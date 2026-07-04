"""Offline tests for the LS-5 code evaluators (scripts/langsmith_evaluators.py)."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from langsmith_evaluators import (  # noqa: E402
    ALL_EVALUATORS,
    eval_audit_event_emitted,
    eval_citations_expectation,
    eval_grounded_matches_expectation,
    eval_has_summary,
    eval_keywords_present,
    eval_latency,
    eval_not_truncated,
    eval_step_quality,
    eval_steps_count,
    eval_stream_well_formed,
    eval_ttft,
    run_code_evaluators,
)

GROUNDED_META = {
    "id": "A1",
    "category": "grounded-core",
    "expect_grounded": True,
    "expect_citations": True,
    "keywords": ["env", "flag"],
}
NEGATIVE_META = {
    "id": "C1",
    "category": "negative",
    "expect_grounded": False,
    "expect_citations": False,
}

GOOD_OUTPUTS = {
    "meta": {"model": "gpt-4.1", "provider": "openai", "grounded_used": True},
    "summary": "Enable Architect mode by setting the LLM_ENABLE_ARCHITECT env flag to true in .env.",
    "steps": [
        "Set LLM_ENABLE_ARCHITECT=true in your .env file",
        "Restart the API so the new flag values are picked up",
    ],
    "citations": [{"source": "docs/config.md"}],
    "audit": {"llm_tokens_completion": 512, "agent_backend": "builtin"},
    "events_seen": ["meta", "summary", "steps", "citations", "audit"],
    "config": {"max_tokens": 1024},
    "timing": {"latency_s": 3.21, "ttft_s": 0.42},
}


def test_good_grounded_run_passes_everything():
    results = {r["key"]: r for fn in ALL_EVALUATORS for r in [fn(GOOD_OUTPUTS, GROUNDED_META)]}
    for key in (
        "has_summary",
        "steps_count",
        "step_quality",
        "grounded_matches_expectation",
        "citations_expectation",
        "keywords_present",
        "audit_event_emitted",
        "stream_well_formed",
        "not_truncated",
    ):
        assert results[key]["score"] == 1, f"{key}: {results[key]}"
    assert results["latency_s"]["score"] == 3.21
    assert results["ttft_s"]["score"] == 0.42


def test_structure_checks_skip_negative_category():
    for fn in (eval_has_summary, eval_steps_count, eval_step_quality):
        assert fn(GOOD_OUTPUTS, NEGATIVE_META)["score"] is None


def test_short_summary_fails():
    outputs = dict(GOOD_OUTPUTS, summary="Too short.")
    assert eval_has_summary(outputs, GROUNDED_META)["score"] == 0


def test_missing_and_short_steps_fail():
    assert eval_steps_count(dict(GOOD_OUTPUTS, steps=["only one step here, quite long"]), GROUNDED_META)["score"] == 0
    assert eval_step_quality(dict(GOOD_OUTPUTS, steps=["tiny", "also tiny"]), GROUNDED_META)["score"] == 0
    assert eval_step_quality(dict(GOOD_OUTPUTS, steps=[]), GROUNDED_META)["score"] == 0


def test_grounded_expectation_mismatch():
    hallucinated = dict(GOOD_OUTPUTS, meta={"grounded_used": True})
    assert eval_grounded_matches_expectation(hallucinated, NEGATIVE_META)["score"] == 0
    assert eval_grounded_matches_expectation(GOOD_OUTPUTS, GROUNDED_META)["score"] == 1
    # C4/C6 style: expect_citations null in jsonl -> no expectation -> skip
    assert eval_grounded_matches_expectation(GOOD_OUTPUTS, {"category": "negative"})["score"] is None


def test_citations_expectation_both_directions():
    assert eval_citations_expectation(dict(GOOD_OUTPUTS, citations=[]), GROUNDED_META)["score"] == 0
    bait_answer = dict(GOOD_OUTPUTS, citations=[])
    assert eval_citations_expectation(bait_answer, NEGATIVE_META)["score"] == 1
    invented = dict(GOOD_OUTPUTS, citations=[{"source": "docs/redis.md"}])
    assert eval_citations_expectation(invented, NEGATIVE_META)["score"] == 0
    assert eval_citations_expectation(GOOD_OUTPUTS, {"expect_citations": None})["score"] is None


def test_keywords_case_insensitive_and_missing():
    assert eval_keywords_present(GOOD_OUTPUTS, GROUNDED_META)["score"] == 1
    meta = dict(GROUNDED_META, keywords=["prometheus"])
    result = eval_keywords_present(GOOD_OUTPUTS, meta)
    assert result["score"] == 0
    assert "prometheus" in result["comment"]
    assert eval_keywords_present(GOOD_OUTPUTS, NEGATIVE_META)["score"] is None


def test_stream_well_formed_requirements_by_category():
    no_steps = dict(GOOD_OUTPUTS, events_seen=["meta", "summary", "audit"])
    assert eval_stream_well_formed(no_steps, GROUNDED_META)["score"] == 0
    # negative category only requires meta + audit
    assert eval_stream_well_formed(dict(GOOD_OUTPUTS, events_seen=["meta", "audit"]), NEGATIVE_META)["score"] == 1
    assert eval_stream_well_formed(dict(GOOD_OUTPUTS, events_seen=["meta"]), NEGATIVE_META)["score"] == 0


def test_audit_event_emitted():
    assert eval_audit_event_emitted(GOOD_OUTPUTS, GROUNDED_META)["score"] == 1
    assert eval_audit_event_emitted(dict(GOOD_OUTPUTS, audit={}), GROUNDED_META)["score"] == 0


def test_not_truncated_detects_cap_hit():
    at_cap = dict(GOOD_OUTPUTS, audit={"llm_tokens_completion": 1024})
    assert eval_not_truncated(at_cap, GROUNDED_META)["score"] == 0
    assert eval_not_truncated(GOOD_OUTPUTS, GROUNDED_META)["score"] == 1
    no_config = dict(GOOD_OUTPUTS, config={})
    assert eval_not_truncated(no_config, GROUNDED_META)["score"] is None
    no_tokens = dict(GOOD_OUTPUTS, audit={})
    assert eval_not_truncated(no_tokens, GROUNDED_META)["score"] is None


def test_timing_metrics_handle_missing_data():
    assert eval_latency(dict(GOOD_OUTPUTS, timing={}), GROUNDED_META)["score"] is None
    assert eval_ttft(dict(GOOD_OUTPUTS, timing={}), GROUNDED_META)["score"] is None


def test_langsmith_adapter_shapes():
    run = SimpleNamespace(outputs=GOOD_OUTPUTS)
    example = SimpleNamespace(metadata=GROUNDED_META)
    feedback = run_code_evaluators(run, example)
    assert len(feedback) == len(ALL_EVALUATORS)
    keys = {f["key"] for f in feedback}
    assert "grounded_matches_expectation" in keys
    for f in feedback:
        assert set(f) == {"key", "score", "comment"}
    # tolerate empty run/example
    empty = run_code_evaluators(SimpleNamespace(outputs=None), SimpleNamespace(metadata=None))
    assert len(empty) == len(ALL_EVALUATORS)


def test_cost_and_tokens_metrics():
    from langsmith_evaluators import eval_completion_tokens, eval_cost

    outputs = dict(GOOD_OUTPUTS, audit={"llm_cost_usd": 0.004834, "llm_tokens_completion": 118})
    assert eval_cost(outputs, GROUNDED_META)["score"] == 0.00483
    assert eval_completion_tokens(outputs, GROUNDED_META)["score"] == 118
    assert eval_cost(dict(GOOD_OUTPUTS, audit={}), GROUNDED_META)["score"] is None
