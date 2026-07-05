"""Backend parity: memory and the feature-request heuristic are wrapper-level,
so switching AGENT_BACKEND can never silently drop them (found 2026-07-04 when
langgraph became the default and both vanished)."""

import json

from app.services import llm_client as llm_mod
from app.services.architect_agent import run_architect_agent


def _scripted_llm(responses, seen=None):
    from itertools import chain, repeat

    it = chain(iter(responses), repeat(responses[-1]))

    def _call(self, messages, model=None, **kwargs):
        if seen is not None:
            seen.append(messages)
        return {
            "text": next(it),
            "provider": "scripted",
            "model": "unit-test",
            "tokens_prompt": 10,
            "tokens_completion": 5,
            "cost_usd": 0.001,
        }

    return _call


def _final(summary, steps=None, flags=None):
    return json.dumps(
        {
            "action": "final",
            "summary": summary,
            "suggested_steps": steps or [],
            "suggested_env_flags": flags or [],
        }
    )


def test_langgraph_persists_and_reads_short_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")
    monkeypatch.setenv("MEMORY_SHORT_ENABLED", "true")
    monkeypatch.setenv("MEMORY_LONG_ENABLED", "false")
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory_short.db"))

    seen = []
    monkeypatch.setattr(
        llm_mod.LLMClient,
        "call",
        _scripted_llm([_final("First answer."), _final("Second answer.")], seen=seen),
    )

    plan1, audit1 = run_architect_agent("First question", session_id="s1", user_id="u1")
    assert audit1["agent_backend"] == "langgraph"
    assert audit1["memory_short_reads"] == 0
    assert audit1["memory_short_writes"] == 2

    plan2, audit2 = run_architect_agent("Second question", session_id="s1", user_id="u1")
    assert audit2["agent_backend"] == "langgraph"
    # both turns of round one are visible on round two
    assert audit2["memory_short_reads"] == 2
    assert audit2["memory_short_writes"] == 2
    # and the conversation context actually reached the langgraph prompt
    round2_messages = seen[-1]
    joined = "\n".join(m["content"] for m in round2_messages)
    assert "Conversation context" in joined
    assert "First answer." in joined


def test_langgraph_memory_isolated_by_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")
    monkeypatch.setenv("MEMORY_SHORT_ENABLED", "true")
    monkeypatch.setenv("MEMORY_LONG_ENABLED", "false")
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory_short.db"))

    monkeypatch.setattr(
        llm_mod.LLMClient, "call", _scripted_llm([_final("Answer.")])
    )

    run_architect_agent("Question A", session_id="s1", user_id="u1")
    _, audit = run_architect_agent("Question B", session_id="s2", user_id="u1")
    assert audit["memory_short_reads"] == 0


def test_langgraph_sets_suggest_feature(monkeypatch):
    # Build/collaborate intent + thin ungrounded plan => feature CTA fires,
    # exactly as it does on the builtin backend.
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")
    monkeypatch.setenv("MEMORY_SHORT_ENABLED", "false")
    monkeypatch.setenv("MEMORY_LONG_ENABLED", "false")

    monkeypatch.setattr(
        llm_mod.LLMClient,
        "call",
        _scripted_llm([_final("We could build that.")]),
    )

    plan, audit = run_architect_agent("Can you add support for webhooks?")
    assert audit["agent_backend"] == "langgraph"
    assert plan.suggest_feature is True
    assert plan.feature_request


def test_builtin_memory_counters_unchanged(monkeypatch, tmp_path):
    # The hoist must not change builtin behavior: same counters, same keys.
    monkeypatch.setenv("AGENT_BACKEND", "builtin")
    monkeypatch.setenv("MEMORY_SHORT_ENABLED", "true")
    monkeypatch.setenv("MEMORY_LONG_ENABLED", "false")
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory_short.db"))

    monkeypatch.setattr(
        llm_mod.LLMClient,
        "call",
        _scripted_llm([json.dumps({"summary": "Builtin answer.", "suggested_steps": []})]),
    )

    _, audit1 = run_architect_agent("First", session_id="s1", user_id="u1")
    assert audit1["agent_backend"] == "builtin"
    assert audit1["memory_short_writes"] == 2
    _, audit2 = run_architect_agent("Second", session_id="s1", user_id="u1")
    assert audit2["memory_short_reads"] == 2
    for key in (
        "memory_short_reads",
        "memory_short_writes",
        "memory_short_pruned",
        "summary_updated",
        "memory_long_reads",
        "memory_long_writes",
        "memory_long_pruned",
    ):
        assert key in audit2
