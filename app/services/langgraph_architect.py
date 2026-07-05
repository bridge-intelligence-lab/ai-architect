"""LangGraph tool-loop architect agent (AGENT_BACKEND=langgraph).

A real agent loop, in contrast to the deterministic linear pipeline in
architect_agent.py: the LLM decides on each turn whether to call a tool
(document retrieval) or finalize the plan, and observations feed back into
the next turn. The graph:

    agent -> (retrieve_docs) -> tools -> agent -> ... -> END

The builtin planner remains the default backend; this path is opt-in and
run_architect_agent falls back to the builtin on any failure here.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from langgraph.graph import END, StateGraph

from app.services.architect_schema import ArchitectPlan
from app.services.llm_client import LLMClient
from app.utils.logger import get_logger

_logger = get_logger("langgraph_architect")

MAX_TOOL_CALLS = 3

_SYSTEM = (
    "You are the solution architect agent for the AI-Architect project. "
    "You work in a loop: on each turn respond ONLY with one JSON object, either\n"
    '  {"action": "retrieve_docs", "query": "<search query>"}\n'
    "to look up project documentation, or\n"
    '  {"action": "final", "summary": "<string>", "suggested_steps": ["..."], '
    '"suggested_env_flags": ["..."]}\n'
    "to finish. Use retrieve_docs when grounding would improve the plan; "
    "finalize once you have enough context. No text outside the JSON object."
)


class AgentState(TypedDict, total=False):
    question: str
    messages: List[Dict[str, str]]
    plan: Dict[str, Any]
    citations: List[Dict[str, Any]]
    tool_calls: int
    pending_query: Optional[str]
    tokens_prompt: int
    tokens_completion: int
    cost_usd: float
    llm_provider: Optional[str]
    llm_model: Optional[str]


def _parse_decision(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("action"):
            return data
    except Exception:
        pass
    # Not a tool-protocol reply: treat the text as a final summary rather
    # than failing the whole run.
    return {"action": "final", "summary": raw[:400]}


_BUDGET_EXHAUSTED = (
    "Retrieval budget exhausted; retrieve_docs is no longer available. "
    'Respond ONLY with the {"action": "final", ...} JSON object now, '
    "building the plan from the context you already have."
)


def _make_agent_node(llm: LLMClient, llm_model: Optional[str]):
    def agent_node(state: AgentState) -> AgentState:
        exhausted = state.get("tool_calls", 0) >= MAX_TOOL_CALLS
        messages = [{"role": "system", "content": _SYSTEM}] + state["messages"]
        if exhausted:
            messages = messages + [{"role": "user", "content": _BUDGET_EXHAUSTED}]
        kwargs: Dict[str, Any] = {}
        if llm_model:
            kwargs["model"] = llm_model
        result = llm.call(messages, **kwargs)
        decision = _parse_decision(result.get("text") or "")

        update: AgentState = {
            "tokens_prompt": state.get("tokens_prompt", 0)
            + int(result.get("tokens_prompt") or 0),
            "tokens_completion": state.get("tokens_completion", 0)
            + int(result.get("tokens_completion") or 0),
            "cost_usd": state.get("cost_usd", 0.0)
            + float(result.get("cost_usd") or 0.0),
            "llm_provider": result.get("provider"),
            "llm_model": result.get("model"),
            "messages": state["messages"]
            + [{"role": "assistant", "content": result.get("text") or ""}],
        }
        if decision.get("action") == "retrieve_docs" and not exhausted:
            update["pending_query"] = str(
                decision.get("query") or state["question"]
            )
        else:
            update["pending_query"] = None
            update["plan"] = {
                "summary": str(decision.get("summary") or ""),
                "suggested_steps": [
                    str(s) for s in (decision.get("suggested_steps") or [])
                ],
                "suggested_env_flags": [
                    str(f) for f in (decision.get("suggested_env_flags") or [])
                ],
            }
        return update

    return agent_node


def _tools_node(state: AgentState) -> AgentState:
    from app.services.doc_retriever import answer_with_citations

    query = state.get("pending_query") or state["question"]
    result = answer_with_citations(query, k=3)
    citations = result.get("citations", [])
    observation = result.get("answer") or "No matching documents."
    return {
        "tool_calls": state.get("tool_calls", 0) + 1,
        "citations": state.get("citations", []) + citations,
        "pending_query": None,
        "messages": state["messages"]
        + [
            {
                "role": "user",
                "content": f"Tool result for retrieve_docs({query!r}):\n{observation}",
            }
        ],
    }


def _route(state: AgentState) -> str:
    return "tools" if state.get("pending_query") else END


def build_graph(llm: LLMClient, llm_model: Optional[str] = None):
    graph = StateGraph(AgentState)
    graph.add_node("agent", _make_agent_node(llm, llm_model))
    graph.add_node("tools", _tools_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _route, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


def run_langgraph_architect(
    question: str,
    session_id: str | None = None,
    user_id: str | None = None,
    llm_model: str | None = None,
    context_blocks: List[str] | None = None,
) -> Tuple[ArchitectPlan, Dict[str, Any]]:
    llm = LLMClient()
    app = build_graph(llm, llm_model)
    # Memory context (loaded by run_architect_agent) rides in as a system
    # message so the tool loop sees conversation history and known facts.
    messages: List[Dict[str, str]] = []
    if context_blocks:
        ctx = "\n\n".join(context_blocks[:3])
        messages.append({"role": "system", "content": f"Context (for grounding):\n{ctx}"})
    messages.append({"role": "user", "content": question})
    final: AgentState = app.invoke(
        {
            "question": question,
            "messages": messages,
            "citations": [],
            "tool_calls": 0,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "cost_usd": 0.0,
        }
    )

    plan_data = final.get("plan") or {}
    if not str(plan_data.get("summary") or "").strip():
        # A retrieve request converted at the cap, or a final with no content.
        # Raising here lets run_architect_agent fall back to the builtin
        # planner instead of streaming an empty plan to the client.
        raise RuntimeError(
            f"langgraph agent produced an empty plan after "
            f"{int(final.get('tool_calls', 0))} tool calls"
        )
    try:
        plan = ArchitectPlan(**plan_data)
    except Exception:
        plan = ArchitectPlan(summary=str(plan_data.get("summary", "")))
    citations = final.get("citations", [])
    if citations:
        plan.citations = citations
        plan.grounded_used = True

    audit: Dict[str, Any] = {
        "agent_backend": "langgraph",
        "agent_tool_calls": int(final.get("tool_calls", 0)),
        "llm_provider": final.get("llm_provider"),
        "llm_model": final.get("llm_model"),
        "llm_tokens_prompt": int(final.get("tokens_prompt", 0)),
        "llm_tokens_completion": int(final.get("tokens_completion", 0)),
        "llm_cost_usd": float(final.get("cost_usd", 0.0)),
        # Memory counters are owned by run_architect_agent (backend-agnostic).
    }
    _logger.info(
        "langgraph architect run",
        extra={"extra": {"tool_calls": audit["agent_tool_calls"]}},
    )
    return plan, audit
