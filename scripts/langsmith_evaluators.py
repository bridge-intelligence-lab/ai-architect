"""Code evaluators for the Architect LangSmith experiments (backlog LS-5).

Deterministic structural checks, ported from scripts/run_live_eval.py and
extended with dataset-metadata-aware checks. LLM-as-judge evaluators (LS-6)
live separately; these run first and are free.

Contract: the experiment target function (scripts/run_langsmith_eval.py)
assembles one output dict per example:

    {
        "meta": {...},            # SSE meta event (model, provider, grounded_used)
        "summary": str | None,    # SSE summary event
        "steps": [str] | None,    # SSE steps event
        "citations": [...],       # SSE citations event
        "audit": {...},           # SSE audit event (tokens, cost, agent_backend)
        "events_seen": [str],     # every SSE event name received, in order
        "config": {               # harness-recorded run config
            "max_tokens": int | None,
        },
        "timing": {
            "latency_s": float | None,
            "ttft_s": float | None,
        },
    }

Example metadata comes from eval/architect_prompts_v2.jsonl via the dataset
(category, expect_grounded, expect_citations, keywords, expected_behavior).

Each evaluator returns {"key", "score", "comment"} with score 1/0 (pass/fail),
a float for informational metrics, or None when the check does not apply to
the example's category (LangSmith renders None as "skipped").
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

SUMMARY_MIN_CHARS = 40
STEPS_MIN_COUNT = 2
STEP_MIN_CHARS = 20

# Structure checks (summary/steps shape) only apply to categories whose
# answers are expected to be full plans; the C-set is judged on behavior.
STRUCTURED_CATEGORIES = ("grounded-core", "new-features")


def _text_blob(outputs: Dict[str, Any]) -> str:
    parts: List[str] = []
    if outputs.get("summary"):
        parts.append(str(outputs["summary"]))
    for step in outputs.get("steps") or []:
        parts.append(str(step))
    return " ".join(parts).lower()


def _is_structured(metadata: Dict[str, Any]) -> bool:
    return metadata.get("category") in STRUCTURED_CATEGORIES


def eval_has_summary(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    if not _is_structured(metadata):
        return {"key": "has_summary", "score": None, "comment": "n/a for this category"}
    length = len((outputs.get("summary") or "").strip())
    return {
        "key": "has_summary",
        "score": int(length >= SUMMARY_MIN_CHARS),
        "comment": f"summary length {length} (min {SUMMARY_MIN_CHARS})",
    }


def eval_steps_count(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    if not _is_structured(metadata):
        return {"key": "steps_count", "score": None, "comment": "n/a for this category"}
    steps = outputs.get("steps") or []
    return {
        "key": "steps_count",
        "score": int(len(steps) >= STEPS_MIN_COUNT),
        "comment": f"{len(steps)} steps (min {STEPS_MIN_COUNT})",
    }


def eval_step_quality(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    if not _is_structured(metadata):
        return {"key": "step_quality", "score": None, "comment": "n/a for this category"}
    steps = outputs.get("steps") or []
    if not steps:
        return {"key": "step_quality", "score": 0, "comment": "no steps"}
    short = [s for s in steps if len(str(s).strip()) < STEP_MIN_CHARS]
    return {
        "key": "step_quality",
        "score": int(not short),
        "comment": f"{len(short)}/{len(steps)} steps under {STEP_MIN_CHARS} chars",
    }


def eval_grounded_matches_expectation(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    expected = metadata.get("expect_grounded")
    if not isinstance(expected, bool):
        return {"key": "grounded_matches_expectation", "score": None, "comment": "no expectation set"}
    actual = (outputs.get("meta") or {}).get("grounded_used")
    return {
        "key": "grounded_matches_expectation",
        "score": int(bool(actual) == expected),
        "comment": f"grounded_used={actual}, expected {expected}",
    }


def eval_citations_expectation(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    expected = metadata.get("expect_citations")
    if not isinstance(expected, bool):
        return {"key": "citations_expectation", "score": None, "comment": "no expectation set"}
    count = len(outputs.get("citations") or [])
    ok = count > 0 if expected else count == 0
    return {
        "key": "citations_expectation",
        "score": int(ok),
        "comment": f"{count} citations, expected {'some' if expected else 'none'}",
    }


def eval_keywords_present(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    keywords = metadata.get("keywords") or []
    if not keywords:
        return {"key": "keywords_present", "score": None, "comment": "no keywords set"}
    blob = _text_blob(outputs)
    missing = [k for k in keywords if str(k).lower() not in blob]
    return {
        "key": "keywords_present",
        "score": int(not missing),
        "comment": f"missing: {missing}" if missing else "all keywords present",
    }


def eval_audit_event_emitted(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    audit = outputs.get("audit") or {}
    return {
        "key": "audit_event_emitted",
        "score": int(bool(audit)),
        "comment": f"audit keys: {len(audit)}",
    }


def eval_stream_well_formed(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    seen = outputs.get("events_seen") or []
    required = {"meta", "audit"}
    if _is_structured(metadata):
        required |= {"summary", "steps"}
    missing = sorted(required - set(seen))
    return {
        "key": "stream_well_formed",
        "score": int(not missing),
        "comment": f"missing events: {missing}" if missing else f"events: {seen}",
    }


def eval_not_truncated(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Flag outputs that hit the completion-token cap (LS-8 max-tokens axis).

    No finish_reason survives the SSE stream, so hitting the cap is inferred
    from llm_tokens_completion >= configured max_tokens.
    """
    max_tokens = (outputs.get("config") or {}).get("max_tokens")
    completion = (outputs.get("audit") or {}).get("llm_tokens_completion")
    if not max_tokens or completion is None:
        return {"key": "not_truncated", "score": None, "comment": "token data unavailable"}
    truncated = int(completion) >= int(max_tokens)
    return {
        "key": "not_truncated",
        "score": int(not truncated),
        "comment": f"completion tokens {completion} / cap {max_tokens}",
    }


def eval_cost(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Surface audit.llm_cost_usd as feedback so experiments aggregate cost."""
    cost = (outputs.get("audit") or {}).get("llm_cost_usd")
    return {
        "key": "cost_usd",
        "score": round(float(cost), 5) if cost is not None else None,
        "comment": "from audit.llm_cost_usd (LiteLLM pricing map)",
    }


def eval_completion_tokens(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    tokens = (outputs.get("audit") or {}).get("llm_tokens_completion")
    return {
        "key": "completion_tokens",
        "score": int(tokens) if tokens is not None else None,
        "comment": "from audit.llm_tokens_completion",
    }


def eval_latency(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    latency = (outputs.get("timing") or {}).get("latency_s")
    return {
        "key": "latency_s",
        "score": round(float(latency), 3) if latency is not None else None,
        "comment": "wall-clock stream duration",
    }


def eval_ttft(outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    ttft = (outputs.get("timing") or {}).get("ttft_s")
    return {
        "key": "ttft_s",
        "score": round(float(ttft), 3) if ttft is not None else None,
        "comment": "time to first SSE event",
    }


ALL_EVALUATORS = [
    eval_has_summary,
    eval_steps_count,
    eval_step_quality,
    eval_grounded_matches_expectation,
    eval_citations_expectation,
    eval_keywords_present,
    eval_audit_event_emitted,
    eval_stream_well_formed,
    eval_not_truncated,
    eval_cost,
    eval_completion_tokens,
    eval_latency,
    eval_ttft,
]


def run_code_evaluators(run, example) -> List[Dict[str, Any]]:
    """LangSmith adapter: summary_evaluator-style entry point.

    `run.outputs` is the target function's payload; `example.metadata` carries
    the dataset expectations. Returns a list of feedback dicts for use with
    langsmith.evaluate(..., evaluators=[run_code_evaluators]).
    """
    outputs: Dict[str, Any] = getattr(run, "outputs", None) or {}
    metadata: Dict[str, Any] = getattr(example, "metadata", None) or {}
    return [fn(outputs, metadata) for fn in ALL_EVALUATORS]
