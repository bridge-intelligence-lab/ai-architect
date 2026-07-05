import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from langchain_core.output_parsers import PydanticOutputParser
from app.services.llm_client import LLMClient
from app.services.architect_schema import ArchitectPlan
from app.services.doc_retriever import answer_with_citations

# Optional LangSmith tracing (env-gated)
from app.utils.logger import get_logger as _get_logger
_arch_logger = _get_logger("architect")
_ENABLE_LS = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true", "yes", "on") and bool(os.getenv("LANGCHAIN_API_KEY"))
_LS_PROJECT = os.getenv("LANGCHAIN_PROJECT")
_LS_SESSION = os.getenv("LANGCHAIN_TRACING_SESSION_NAME")
try:
    if _ENABLE_LS:
        from langsmith.run_trees import RunTree as _LSRunTree  # type: ignore
    else:
        _LSRunTree = None  # type: ignore
except Exception:
    _LSRunTree = None  # type: ignore


def _build_messages(question: str, plan_parser: PydanticOutputParser, context_blocks: List[str] | None = None) -> List[Dict[str, str]]:
    context_blocks = context_blocks or []
    fmt = plan_parser.get_format_instructions()
    system = (
        "You are the solution architect assistant for the AI-Architect project. "
        "Respond ONLY with a JSON object that matches the provided schema. "
        "Your JSON MUST include both 'summary' (string) and 'suggested_steps' (array of strings). "
        "If you cannot provide a value, set summary to an empty string and suggested_steps to an empty array. "
        "Do not include any fields outside the schema; do not include explanations outside JSON."
    )
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "system", "content": fmt},
    ]
    if context_blocks:
        ctx = "\n\n".join(context_blocks[:3])  # keep concise
        messages.append({"role": "system", "content": f"Context (for grounding):\n{ctx}"})
    messages.append({"role": "user", "content": question})
    return messages


def _memory_debug(e: Exception) -> None:
    if os.getenv("MEMORY_DEBUG", "").lower() in ("1", "true", "yes", "on"):
        try:
            print(f"[MEMORY_DEBUG] memory op error: {e}")
        except Exception:
            pass


def _load_memory_context(
    uid: str, sid: str, question: str, short_enabled: bool, long_enabled: bool
) -> Tuple[List[str], Dict[str, int]]:
    """Load short/long memory into context blocks. Backend-agnostic."""
    blocks: List[str] = []
    counters = {
        "memory_short_reads": 0,
        "memory_short_pruned": 0,
        "memory_long_reads": 0,
        "memory_long_pruned": 0,
    }

    if short_enabled:
        try:
            from app.memory.short_memory import init_short_memory, load_summary, load_turns

            init_short_memory()
            turns = load_turns(uid, sid)
            counters["memory_short_reads"] = len(turns)
            counters["memory_short_pruned"] = int(getattr(load_turns, "_last_pruned", 0))
            prefix = load_summary(uid, sid) or "\n".join(f"{r}: {c}" for r, c in turns[-5:])  # last 5 turns
            if prefix:
                blocks.append(f"Conversation context:\n{prefix}")
        except Exception as e:
            _memory_debug(e)

    if long_enabled:
        try:
            from app.memory.long_memory import retrieve_facts

            facts = retrieve_facts(uid, question, top_k=5)
            counters["memory_long_reads"] = len(facts)
            counters["memory_long_pruned"] = int(getattr(retrieve_facts, "_last_pruned", 0))
            if facts:
                snippet = "\n".join(f"- {f['text']}" for f in facts)
                blocks.append(f"Relevant background facts:\n{snippet}")
        except Exception as e:
            _memory_debug(e)

    return blocks, counters


def _save_memory(
    uid: str, sid: str, question: str, plan: ArchitectPlan, short_enabled: bool, long_enabled: bool
) -> Dict[str, Any]:
    """Persist the turn to short/long memory. Backend-agnostic."""
    counters: Dict[str, Any] = {
        "memory_short_writes": 0,
        "summary_updated": False,
        "memory_long_writes": 0,
    }

    if short_enabled:
        try:
            from app.memory.short_memory import save_turn, update_summary_if_needed

            save_turn(uid, sid, "user", question)
            assistant_response = plan.summary or "Generated architecture plan."
            save_turn(uid, sid, "assistant", assistant_response)
            counters["memory_short_writes"] = 2
            counters["summary_updated"] = update_summary_if_needed(uid, sid)
        except Exception as e:
            _memory_debug(e)

    if long_enabled:
        try:
            from app.memory.long_memory import ingest_fact

            if plan.summary and len(plan.summary) > 50:
                ingest_fact(uid, plan.summary)
                counters["memory_long_writes"] += 1
            for step in (plan.suggested_steps or []):
                if len(step) > 50:
                    ingest_fact(uid, step)
                    counters["memory_long_writes"] += 1
            if plan.feature_request and len(plan.feature_request) > 50:
                ingest_fact(uid, plan.feature_request)
                counters["memory_long_writes"] += 1
        except Exception as e:
            _memory_debug(e)

    return counters


# Explicit build/collaborate phrasing fires the CTA even when the answer is
# grounded and has steps: with vector RAG + a strong model nearly every answer
# is grounded, so the sparse-or-ungrounded gate alone never triggers.
_FEATURE_PHRASES = (
    "add support",
    "can you add",
    "could you add",
    "can we add",
    "please add",
    "can we build",
    "can you build",
    "could we build",
    "build that together",
    "build this together",
    "work on this together",
    "feature request",
    "new feature",
    "would be nice",
    "would be great",
    "on the roadmap",
    "do you plan",
    "any plans",
    "integrate this with",
    "integrate it with",
    "integration with",
)


def _apply_feature_heuristic(plan: ArchitectPlan, question: str) -> None:
    """Suggest opening a feature request when the ask sounds like new work:
    explicit build/collaborate phrasing always fires; broad keywords only fire
    when the plan came back thin or ungrounded. Backend-agnostic."""
    try:
        ql = (question or "").lower()
        explicit = any(p in ql for p in _FEATURE_PHRASES)
        needs = any(w in ql for w in ("feature", "support", "integrate", "add", "roadmap"))
        sparse = len(plan.suggested_steps or []) == 0 and len(plan.suggested_env_flags or []) == 0
        grounded_used = bool(getattr(plan, "grounded_used", False))
        if explicit or ((sparse or not grounded_used) and needs):
            plan.suggest_feature = True
            plan.feature_request = plan.feature_request or (
                f"Request: {question[:60]}" if question else "Feature request"
            )
            plan.tone_hint = plan.tone_hint or ("exploratory" if not grounded_used else "actionable")
    except Exception as e:
        _memory_debug(e)


def run_architect_agent(question: str, session_id: str | None = None, user_id: str | None = None, llm_model: str | None = None) -> Tuple[ArchitectPlan, Dict[str, Any]]:
    """Backend-agnostic entrypoint: memory load/save and the feature-request
    heuristic live here so every backend gets them; only planning is
    backend-specific (AGENT_BACKEND=builtin|langgraph, builtin the default
    and the fallback on any langgraph failure)."""
    short_enabled = os.getenv("MEMORY_SHORT_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    long_enabled = os.getenv("MEMORY_LONG_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    uid = user_id or "anonymous"
    sid = session_id or "default"

    memory_blocks, read_counters = _load_memory_context(uid, sid, question, short_enabled, long_enabled)

    plan = None
    audit: Dict[str, Any] = {}
    if os.getenv("AGENT_BACKEND", "builtin").lower() == "langgraph":
        try:
            from app.services.langgraph_architect import run_langgraph_architect

            plan, audit = run_langgraph_architect(
                question,
                session_id=session_id,
                user_id=user_id,
                llm_model=llm_model,
                context_blocks=memory_blocks or None,
            )
        except Exception as e:
            _arch_logger.warning(
                "langgraph backend failed; using builtin",
                extra={"extra": {"error": str(e)}},
            )
            plan = None

    if plan is None:
        plan, audit = _run_builtin_planner(question, memory_blocks, llm_model, read_counters)

    _apply_feature_heuristic(plan, question)
    write_counters = _save_memory(uid, sid, question, plan, short_enabled, long_enabled)
    audit.update(read_counters)
    audit.update(write_counters)
    return plan, audit


def _run_builtin_planner(
    question: str,
    memory_blocks: List[str],
    llm_model: str | None,
    read_counters: Dict[str, int],
) -> Tuple[ArchitectPlan, Dict[str, Any]]:
    original_question = question

    # 1) Retrieval
    citations: List[Dict[str, Any]] = []
    rag_meta: Dict[str, Any] = {}

    docs_path = os.getenv("DOCS_PATH") or "./docs"
    os.environ["DOCS_PATH"] = docs_path
    rag = answer_with_citations(question, k=3)
    citations = rag.get("citations", [])
    for k in ("rag_multi_query", "rag_multi_count", "rag_hyde"):
        if k in rag:
            rag_meta[k] = rag[k]

    grounded_used = bool(citations)
    rag_lines: List[str] = []
    if grounded_used:
        # Make compact context lines
        for c in citations[:3]:
            title = c.get("source") or c.get("path") or "doc"
            snippet = (c.get("snippet") or "").strip().replace("\n", " ")
            if snippet:
                snippet = snippet[:400]
            rag_lines.append(f"- {title}: {snippet}")

    # Build final context blocks: memory (short + long), then RAG
    final_context: List[str] = list(memory_blocks)
    if grounded_used and rag_lines:
        final_context.append("Grounding:\n" + "\n".join(rag_lines))

    # 2) Build messages with structured format instructions
    parser = PydanticOutputParser(pydantic_object=ArchitectPlan)
    messages = _build_messages(original_question, parser, final_context if final_context else None)

    # 3) Call LLM
    llm = LLMClient()

    # Optional: start LangSmith run
    ls_run = None
    ls_run_id = None
    if _LSRunTree:
        try:
            _arch_logger.info("ls.run_tree start", extra={"extra": {"project": _LS_PROJECT, "session": _LS_SESSION}})
            ls_inputs = {"question": original_question, "context_blocks": final_context}
            ls_run = _LSRunTree(name="architect_server", run_type="chain", project=_LS_PROJECT, inputs=ls_inputs)
            ls_run_id = getattr(ls_run, "id", None)
            ls_run.post()
            _arch_logger.info("ls.run_tree posted", extra={"extra": {"run_id": ls_run_id}})
        except Exception as _e:
            _arch_logger.info("ls.run_tree failed", extra={"extra": {"error": str(_e)}})
            ls_run = None

    call_kwargs: Dict[str, Any] = {}
    if llm_model:
        call_kwargs["model"] = llm_model
    result = llm.call(messages, **call_kwargs)

    # 4) Parse structured output (fallback to defaults on error)
    text = result.get("text") or ""
    try:
        plan = parser.parse(text)
    except Exception:
        # fallback: try to construct directly if text is already JSON-like
        try:
            import json as _json

            data = _json.loads(text) if isinstance(text, str) else {}
            plan = ArchitectPlan(**data) if isinstance(data, dict) else ArchitectPlan()
        except Exception:
            plan = ArchitectPlan()

    # Post-parse guardrails: ensure fields are non-null, but do not synthesize content
    try:
        if getattr(plan, "summary", None) is None:
            plan.summary = ""
        if getattr(plan, "suggested_steps", None) is None:
            plan.suggested_steps = []
    except Exception:
        # Never fail the request due to guardrail adjustments
        pass

    # 5) Attach citations if grounded
    if grounded_used:
        plan.citations = citations
        plan.grounded_used = True

    # Complete LangSmith run with outputs (if enabled)
    if ls_run and ls_run_id:
        try:
            ls_outputs = {
                "summary": plan.summary,
                "steps": plan.suggested_steps,
                "citations": plan.citations,
                "audit": {
                    "llm_model": llm_model or llm.model,
                    "memory_short_reads": read_counters.get("memory_short_reads", 0),
                    "memory_long_reads": read_counters.get("memory_long_reads", 0),
                },
            }
            ls_run.end(outputs=ls_outputs, end_time=datetime.now(timezone.utc))
            _arch_logger.info("ls.run_tree end ok", extra={"extra": {"run_id": ls_run_id}})
        except Exception as _e:
            _arch_logger.info("ls.run_tree end failed", extra={"extra": {"error": str(_e), "run_id": ls_run_id}})

    # 6) Build audit fields (memory counters are added by run_architect_agent)
    audit: Dict[str, Any] = {
        "agent_backend": "builtin",
        "llm_provider": result.get("provider"),
        "llm_model": result.get("model"),
        "llm_tokens_prompt": result.get("tokens_prompt"),
        "llm_tokens_completion": result.get("tokens_completion"),
        "llm_cost_usd": result.get("cost_usd"),
        **rag_meta,
    }

    return plan, audit
