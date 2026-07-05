"""Risk scoring: keyword-based heuristics and optional deterministic ML."""
import os
from typing import Dict, Tuple

from app.utils.logger import get_logger

# Simple heuristic risk scorer with optional ML path.


logger = get_logger()

RISK_KEYWORDS = {
    "high": [
        "breach",
        "violation",
        "non-compliant",
        "lawsuit",
        "penalty",
        "critical",
        "severe",
    ],
    "medium": [
        "exposure",
        "incident",
        "warning",
        "vulnerability",
        "moderate",
    ],
    "low": [
        "info",
        "advisory",
        "minor",
        "low",
    ],
}


def _env_truthy(name: str, default: str = "false") -> bool:
    """Parse boolean-like environment variables robustly."""
    val = os.getenv(name, default)
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "on", "y"}


def heuristic_score(text: str) -> Dict[str, object]:
    """Score text by keyword membership in risk tiers; return (label, value, rationale, method)."""
    t = (text or "").lower()
    score = 0.0
    label = "low"
    rationale = []

    if any(k in t for k in RISK_KEYWORDS["high"]):
        score = 0.9
        label = "high"
        rationale.append("matched high-risk keywords")
    elif any(k in t for k in RISK_KEYWORDS["medium"]):
        score = 0.6
        label = "medium"
        rationale.append("matched medium-risk keywords")
    else:
        score = 0.2
        label = "low"
        rationale.append("no strong risk indicators")

    return {
        "label": label,
        "value": score,
        "rationale": "; ".join(rationale),
        "method": "heuristic",
    }


def _deterministic_ml_score(text: str, threshold: float) -> Tuple[str, float, str]:
    """A tiny, deterministic scorer that mimics an ML model.

    It computes a simple feature: proportion of characters that are in risky keywords,
    plus length normalization. Then maps to [0,1] and applies threshold.
    This avoids external dependencies while allowing flag-based behavior.
    """
    t = (text or "").lower()
    # Features (deterministic, simple)
    risky_tokens = set(RISK_KEYWORDS["high"] + RISK_KEYWORDS["medium"])  # type: ignore[index]
    token_hits = sum(1 for tok in risky_tokens if tok in t)
    length = max(len(t), 1)
    raw = min(1.0, (token_hits * 0.45) + (min(length, 500) / 500.0) * 0.2)
    # map to [0,1]
    value = max(0.0, min(1.0, raw))
    label = (
        "high"
        if value >= threshold
        else ("medium" if value >= (threshold * 0.75) else "low")
    )
    return label, value, "ml"


def score(text: str) -> Dict[str, object]:
    """Score text using ML (if RISK_ML_ENABLED) or heuristic method."""
    # If ML enabled, compute deterministic pseudo-ML score; else heuristic
    ml_enabled = _env_truthy("RISK_ML_ENABLED", "false")
    try:
        threshold = float(os.getenv("RISK_THRESHOLD", "0.6"))
    except Exception:
        threshold = 0.6

    if ml_enabled:
        label, value, method = _deterministic_ml_score(text, threshold)
        logger.info(
            "{'event': 'risk_env', 'ml_enabled': %s, 'threshold': %s}",
            ml_enabled,
            threshold,
        )
        logger.info(
            "{'event': 'risk_score', 'method': '%s', 'threshold': %s}",
            method,
            threshold,
        )
        return {
            "label": label,
            "value": value,
            "rationale": f"threshold={threshold}",
            "method": method,
        }

    # Heuristic path
    result = heuristic_score(text)
    logger.info(
        "{'event': 'risk_env', 'ml_enabled': %s, 'threshold': %s}",
        ml_enabled,
        threshold,
    )
    logger.info(
        "{'event': 'risk_score', 'method': '%s'}",
        result.get("method", "heuristic"),
    )
    return result
