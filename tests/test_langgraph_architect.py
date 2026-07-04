"""LangGraph tool-loop agent (AGENT_BACKEND=langgraph)."""

import json

from app.services import llm_client as llm_mod
from app.services.architect_agent import run_architect_agent


def _scripted_llm(responses):
    """Return a fake LLMClient.call that plays back scripted texts.

    After the script is exhausted the last response repeats, so a builtin
    fallback path that makes extra LLM calls does not hit StopIteration.
    """
    from itertools import chain, repeat

    it = chain(iter(responses), repeat(responses[-1]))

    def _call(self, messages, model=None, **kwargs):
        return {
            "text": next(it),
            "provider": "scripted",
            "model": "unit-test",
            "tokens_prompt": 10,
            "tokens_completion": 5,
            "cost_usd": 0.001,
        }

    return _call


def test_langgraph_tool_loop_retrieves_then_finalizes(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "rbac.txt").write_text(
        "RBAC roles are parsed from the X-User-Role header and gate grounded queries."
    )
    monkeypatch.setenv("DOCS_PATH", str(docs))
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")

    monkeypatch.setattr(
        llm_mod.LLMClient,
        "call",
        _scripted_llm(
            [
                json.dumps({"action": "retrieve_docs", "query": "RBAC roles"}),
                json.dumps(
                    {
                        "action": "final",
                        "summary": "Use header-based RBAC.",
                        "suggested_steps": ["parse role header", "gate grounded"],
                        "suggested_env_flags": ["RBAC_ENABLED"],
                    }
                ),
            ]
        ),
    )

    plan, audit = run_architect_agent("How does RBAC work?")

    assert audit["agent_backend"] == "langgraph"
    assert audit["agent_tool_calls"] == 1
    assert plan.summary == "Use header-based RBAC."
    assert plan.suggested_steps == ["parse role header", "gate grounded"]
    assert plan.grounded_used is True
    assert any("rbac" in (c.get("source") or "").lower() for c in plan.citations)
    # token/cost accounting accumulates across both LLM turns
    assert audit["llm_tokens_prompt"] == 20
    assert abs(audit["llm_cost_usd"] - 0.002) < 1e-9


def test_langgraph_finalizes_without_tools(monkeypatch):
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")
    monkeypatch.setattr(
        llm_mod.LLMClient,
        "call",
        _scripted_llm([json.dumps({"action": "final", "summary": "Direct answer."})]),
    )

    plan, audit = run_architect_agent("Simple question")
    assert audit["agent_backend"] == "langgraph"
    assert audit["agent_tool_calls"] == 0
    assert plan.summary == "Direct answer."
    assert plan.grounded_used is False


def test_langgraph_non_protocol_reply_becomes_summary(monkeypatch):
    # A model that ignores the JSON protocol still yields a plan, not a crash.
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")
    monkeypatch.setattr(
        llm_mod.LLMClient, "call", _scripted_llm(["Just some prose answer."])
    )

    plan, audit = run_architect_agent("Whatever")
    assert audit["agent_backend"] == "langgraph"
    assert plan.summary == "Just some prose answer."


def test_langgraph_tool_call_cap_warns_then_finalizes(monkeypatch, tmp_path):
    # The agent asks for tools until the cap; once told the budget is gone
    # it must produce a real final plan, not an empty one.
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("alpha beta gamma")
    monkeypatch.setenv("DOCS_PATH", str(docs))
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")

    seen_prompts = []
    retrieve = json.dumps({"action": "retrieve_docs", "query": "alpha"})
    final = json.dumps({"action": "final", "summary": "Plan built from gathered context."})
    it = iter([retrieve, retrieve, retrieve, final])

    def _call(self, messages, model=None, **kwargs):
        seen_prompts.append(messages)
        return {
            "text": next(it),
            "provider": "scripted",
            "model": "unit-test",
            "tokens_prompt": 10,
            "tokens_completion": 5,
            "cost_usd": 0.001,
        }

    monkeypatch.setattr(llm_mod.LLMClient, "call", _call)

    plan, audit = run_architect_agent("Loop forever?")
    assert audit["agent_backend"] == "langgraph"
    assert audit["agent_tool_calls"] == 3  # MAX_TOOL_CALLS
    assert plan.summary == "Plan built from gathered context."
    # the 4th LLM turn (post-cap) must carry the budget-exhausted instruction
    last_turn = seen_prompts[-1]
    assert any("budget exhausted" in m["content"].lower() for m in last_turn)


def test_langgraph_empty_plan_falls_back_to_builtin(monkeypatch, tmp_path):
    # A model that ignores the budget warning and keeps requesting tools
    # must not surface an empty plan: the builtin planner takes over.
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("alpha beta gamma")
    monkeypatch.setenv("DOCS_PATH", str(docs))
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")

    endless = [json.dumps({"action": "retrieve_docs", "query": "alpha"})] * 10
    monkeypatch.setattr(llm_mod.LLMClient, "call", _scripted_llm(endless))

    plan, audit = run_architect_agent("Loop forever?")
    # what matters: the empty langgraph plan never reaches the client
    assert audit["agent_backend"] == "builtin"


def test_langgraph_empty_final_summary_falls_back_to_builtin(monkeypatch):
    # An immediate final with no summary is an empty plan too.
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")
    monkeypatch.setattr(
        llm_mod.LLMClient,
        "call",
        _scripted_llm([json.dumps({"action": "final", "summary": ""})]),
    )

    plan, audit = run_architect_agent("Empty final")
    assert audit["agent_backend"] == "builtin"


def test_default_backend_is_builtin(monkeypatch):
    monkeypatch.delenv("AGENT_BACKEND", raising=False)
    plan, audit = run_architect_agent("What is this project?")
    assert audit["agent_backend"] == "builtin"


def test_langgraph_failure_falls_back_to_builtin(monkeypatch):
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")
    import app.services.langgraph_architect as lg

    def _boom(*a, **k):
        raise RuntimeError("graph exploded")

    monkeypatch.setattr(lg, "run_langgraph_architect", _boom)
    plan, audit = run_architect_agent("Resilience check")
    assert audit["agent_backend"] == "builtin"
