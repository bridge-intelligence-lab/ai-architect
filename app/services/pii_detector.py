import os
import re
from typing import Any, Dict, List

# Simple, deterministic PII detector using regex/heuristics.
# Returns masked previews and basic counts, no external calls.


def _mask(value: str, head: int = 2, tail: int = 2) -> str:
    if not value:
        return value
    if len(value) <= head + tail:
        return "*" * len(value)
    return value[:head] + "*" * (len(value) - head - tail) + value[-tail:]


def _luhn_check(num: str) -> bool:
    s = [int(ch) for ch in re.sub(r"\D", "", num)]
    total = 0
    double = False
    for d in reversed(s):
        if double:
            d = d * 2
            if d > 9:
                d -= 9
        total += d
        double = not double
    return total % 10 == 0 if s else False


# Base patterns (always available; activation controlled by PII_TYPES/PII_LOCALES)
BASE_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # US-style phone plus E.164-like international (+CC and 7-14 digits with optional separators)
    "phone": re.compile(
        r"\b(?:\+\d{1,3}[ -]?)?(?:\(?\d{2,4}\)?[ -]?\d{3,4}[ -]?\d{3,4})\b"
    ),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "ipv6": re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b"),  # simplified
    "iban": re.compile(r"\b[A-Za-z]{2}[0-9A-Za-z]{13,32}\b"),  # simplified, no checksum
    "passport": re.compile(r"\b[0-9A-Za-z]{7,9}\b"),  # generic heuristic
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
}

# Locale-specific examples (simplified). These are illustrative and may have false positives.
LOCALE_PATTERNS = {
    "US": {
        # ZIP and ZIP+4
        "postal_us": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
        # A few driver license formats vary by state; keep generic illustrative pattern (7-9 alphanum)
        "dl_us": re.compile(r"\b[A-Za-z0-9]{7,9}\b"),
    },
    "UK": {
        # UK postcode (simplified, broad)
        "postal_uk": re.compile(
            r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b", re.IGNORECASE
        ),
        # NI number: two letters, six digits, optional letter A-D
        "ni_uk": re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]?\b", re.IGNORECASE),
    },
    "CA": {
        # Canadian SIN (very simplified): 9 digits, allow spaces
        "sin_ca": re.compile(
            r"\b\d[ -]?\d[ -]?\d[ -]?\d[ -]?\d[ -]?\d[ -]?\d[ -]?\d[ -]?\d\b"
        ),
        # Canadian postal code: A1A 1A1
        "postal_ca": re.compile(
            r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z]\s?\d[ABCEGHJ-NPRSTV-Z]\d\b",
            re.IGNORECASE,
        ),
    },
    "DE": {
        # German Personalausweis not standardized for regex; include 9-10 alphanum as placeholder
        "id_de": re.compile(r"\b[0-9A-Za-z]{9,10}\b"),
        # German postal code: 5 digits
        "postal_de": re.compile(r"\b\d{5}\b"),
    },
}

ACTIVE_DEFAULT = ["email", "phone", "ssn", "credit_card", "ipv4"]


def _active_types_from_env() -> List[str]:
    raw = os.getenv("PII_TYPES", ",".join(ACTIVE_DEFAULT))
    return [t.strip() for t in raw.split(",") if t.strip()]


def _active_locales_from_env() -> List[str]:
    raw = os.getenv("PII_LOCALES", "")
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def _compile_active_patterns(types_override: list[str] | None = None, locales_override: list[str] | None = None) -> Dict[str, re.Pattern]:
    pats: Dict[str, re.Pattern] = {}
    active_types = set(types_override if types_override is not None else _active_types_from_env())
    # base
    for name, pat in BASE_PATTERNS.items():
        if name in active_types:
            pats[name] = pat
    # locale
    active_locales = set((t.strip().upper() for t in (locales_override or []))) if locales_override is not None else set(_active_locales_from_env())
    for loc in active_locales:
        for lname, pat in LOCALE_PATTERNS.get(loc, {}).items():
            # expose with plain type names but keep locale suffix
            pats[lname] = pat
    return pats


def detect_pii(text: str, types: list[str] | None = None, locales: list[str] | None = None) -> Dict[str, Any]:
    # Optional Presidio backend (PII_BACKEND=presidio); the regex baseline
    # below stays the default and the fallback when Presidio is not
    # installed or fails (e.g. missing spaCy model).
    if os.getenv("PII_BACKEND", "regex").lower() == "presidio":
        try:
            from app.services.pii_presidio import detect_pii_presidio

            result = detect_pii_presidio(text, types=types)
            result["pii_backend"] = "presidio"
            return result
        except Exception:
            pass

    entities: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}

    # Compile active patterns on each call to respect dynamic env changes in tests/runtime
    active_patterns = _compile_active_patterns(types_override=types, locales_override=locales)

    sample = (text or "")[:5000]
    for ptype, pat in active_patterns.items():
        # respect request-level types override too; otherwise env-based defaults
        base_types = set(types or _active_types_from_env())
        if ptype in BASE_PATTERNS and ptype not in base_types:
            continue
        for m in pat.finditer(sample):
            val = m.group(0)
            if ptype == "credit_card" and not _luhn_check(val):
                continue
            counts[ptype] = counts.get(ptype, 0) + 1
            entities.append(
                {
                    "type": ptype,
                    "value_preview": _mask(val),
                    "span": [m.start(), m.end()],
                }
            )

    types_present = sorted(list(counts.keys()))
    return {
        "entities": entities,
        "types_present": types_present,
        "counts": counts,
        "total": len(entities),
        "pii_backend": "regex",
    }
