"""LLM-as-judge evaluators for the Architect LangSmith experiments (LS-6).

Four judges, each scoring 1-5 with reasoning, via litellm (same dependency the
app uses). Judge prompts are versioned here in code so calibration (LS-7)
shows up as reviewable diffs.

Judges read the target payload (see scripts/langsmith_evaluators.py for the
contract) and the dataset example metadata. The C-set's `expected_behavior`
text is passed to the judge verbatim, so hallucination-bait prompts are judged
against "should say it doesn't exist", not against generic helpfulness.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "gpt-4.1-mini")

_SYSTEM = (
    "You are a strict evaluation judge for an AI assistant that answers "
    "questions about the ai-architect codebase. Score the given dimension "
    "from 1 (very poor) to 5 (excellent). Be skeptical: unsupported or "
    "invented claims must lose points. Respond ONLY with JSON: "
    '{"score": <1-5>, "reasoning": "<2-3 sentences>"}'
)

_DIMENSIONS: Dict[str, str] = {
    "judge_correctness": (
        "CORRECTNESS: Are the factual claims in the answer consistent with "
        "the retrieved context (citations/snippets)? Claims that contradict "
        "the context, or specifics (env vars, file paths, endpoints) that "
        "appear in neither the context nor the question, score low. If the "
        "expected behavior says the feature does not exist, a correct answer "
        "says so plainly."
    ),
    "judge_groundedness": (
        "GROUNDEDNESS: Is every concrete claim supported by the retrieved "
        "context? An answer that invents configuration, files, or endpoints "
        "not present in the context scores 1-2, even if plausible. An answer "
        "that stays within the context, or explicitly says the information "
        "is not available, scores high."
    ),
    "judge_completeness": (
        "COMPLETENESS: Does the answer address every part of the question? "
        "Partial answers that silently drop sub-questions score low. If the "
        "answer appears cut off mid-thought, score 1-2 and say so."
    ),
    "judge_actionability": (
        "ACTIONABILITY: Could an engineer follow the suggested steps without "
        "guessing? Steps must be concrete (which file, which flag, which "
        "command). Vague advice ('configure appropriately') scores low. For "
        "questions where refusing or asking for clarification is the right "
        "move, a clear refusal/clarification is fully actionable."
    ),
}


def _render_payload(outputs: Dict[str, Any]) -> str:
    citations = outputs.get("citations") or []
    ctx_lines = []
    for c in citations[:10]:
        if isinstance(c, dict):
            ctx_lines.append(f"- {c.get('source')}: {str(c.get('snippet'))[:300]}")
    return json.dumps(
        {
            "summary": outputs.get("summary"),
            "steps": outputs.get("steps"),
            "grounded_used": (outputs.get("meta") or {}).get("grounded_used"),
        },
        ensure_ascii=False,
    ) + ("\n\nRetrieved context:\n" + "\n".join(ctx_lines) if ctx_lines else "\n\nRetrieved context: (none)")


def _judge_once(dimension_key: str, question: str, outputs: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    import litellm

    expected = metadata.get("expected_behavior")
    user = (
        f"Dimension to score:\n{_DIMENSIONS[dimension_key]}\n\n"
        f"Question asked:\n{question}\n\n"
        + (f"Expected behavior for this test case:\n{expected}\n\n" if expected else "")
        + f"Assistant answer payload:\n{_render_payload(outputs)}"
    )
    resp = litellm.completion(
        model=JUDGE_MODEL,
        messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        temperature=0.0,
        max_tokens=300,
        response_format={"type": "json_object"},
    )
    parsed = json.loads(resp.choices[0].message.content)
    score = max(1, min(5, int(parsed.get("score", 0))))
    return {"key": dimension_key, "score": score, "comment": str(parsed.get("reasoning", ""))[:500]}


def _make_judge(dimension_key: str):
    def _evaluator(run, example) -> Dict[str, Any]:
        outputs: Dict[str, Any] = getattr(run, "outputs", None) or {}
        metadata: Dict[str, Any] = getattr(example, "metadata", None) or {}
        question: str = ((getattr(example, "inputs", None) or {}).get("question")) or ""
        try:
            return _judge_once(dimension_key, question, outputs, metadata)
        except Exception as exc:  # judge failure must not sink the experiment
            return {"key": dimension_key, "score": None, "comment": f"judge error: {exc}"}

    _evaluator.__name__ = dimension_key
    return _evaluator


judge_correctness = _make_judge("judge_correctness")
judge_groundedness = _make_judge("judge_groundedness")
judge_completeness = _make_judge("judge_completeness")
judge_actionability = _make_judge("judge_actionability")

ALL_JUDGES = [judge_correctness, judge_groundedness, judge_completeness, judge_actionability]
