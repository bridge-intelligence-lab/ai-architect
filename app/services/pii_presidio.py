"""Presidio-backed PII detection (PII_BACKEND=presidio).

Optional backend using Microsoft Presidio's AnalyzerEngine (NER +
pattern recognizers) instead of the regex baseline. Returns the same
shape as pii_detector.detect_pii. Presidio is an optional dependency
(`pip install .[presidio]` plus a spaCy model); the caller falls back to
the regex baseline when it is unavailable or fails.
"""

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

# Our type names -> Presidio entity names
TYPE_TO_PRESIDIO = {
    "email": "EMAIL_ADDRESS",
    "phone": "PHONE_NUMBER",
    "ssn": "US_SSN",
    "credit_card": "CREDIT_CARD",
    "iban": "IBAN_CODE",
    "ipv4": "IP_ADDRESS",
    "ipv6": "IP_ADDRESS",
    "passport": "US_PASSPORT",
    "person": "PERSON",
    "location": "LOCATION",
}
PRESIDIO_TO_TYPE = {
    "EMAIL_ADDRESS": "email",
    "PHONE_NUMBER": "phone",
    "US_SSN": "ssn",
    "CREDIT_CARD": "credit_card",
    "IBAN_CODE": "iban",
    "IP_ADDRESS": "ipv4",
    "US_PASSPORT": "passport",
    "PERSON": "person",
    "LOCATION": "location",
}


def _threshold() -> float:
    try:
        return float(os.getenv("PII_PRESIDIO_THRESHOLD", "0.5"))
    except Exception:
        return 0.5


@lru_cache(maxsize=1)
def _analyzer():
    """Build the AnalyzerEngine once; spaCy model via PII_SPACY_MODEL."""
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    model = os.getenv("PII_SPACY_MODEL", "en_core_web_sm")
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": model}],
        }
    )
    return AnalyzerEngine(nlp_engine=provider.create_engine())


def detect_pii_presidio(
    text: str, types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Analyze text with Presidio; same return shape as the regex baseline.

    Raises on any Presidio/spaCy failure; the dispatcher in pii_detector
    handles the fallback.
    """
    from app.services.pii_detector import _mask

    sample = (text or "")[:5000]
    wanted = None
    if types:
        wanted = sorted(
            {TYPE_TO_PRESIDIO[t] for t in types if t in TYPE_TO_PRESIDIO}
        )

    results = _analyzer().analyze(text=sample, language="en", entities=wanted)

    threshold = _threshold()
    entities: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for r in results:
        if r.score < threshold:
            continue
        ptype = PRESIDIO_TO_TYPE.get(r.entity_type, r.entity_type.lower())
        counts[ptype] = counts.get(ptype, 0) + 1
        entities.append(
            {
                "type": ptype,
                "value_preview": _mask(sample[r.start : r.end]),
                "span": [r.start, r.end],
                "score": round(float(r.score), 3),
            }
        )

    return {
        "entities": entities,
        "types_present": sorted(counts.keys()),
        "counts": counts,
        "total": len(entities),
    }
