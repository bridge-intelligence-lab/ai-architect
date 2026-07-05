"""Intent router: keyword rules + builtin heuristics to classify user queries."""
import json
import os
from typing import Any, Dict, List, Literal

Intent = Literal[
    "qa", "pii_detect", "risk_score", "policy_navigator", "pii_remediation", "other"
]

_RULES_CACHE: Dict[str, Any] | None = None
_BACKEND_NAME = "rules"
_BACKEND_VERSION = "v2"


def is_enabled() -> bool:
    return os.getenv("ROUTER_ENABLED", "false").lower() in ("1", "true", "yes", "on")


def _load_rules() -> Dict[str, Any]:
    global _RULES_CACHE
    if _RULES_CACHE is not None:
        return _RULES_CACHE
    rules_json = os.getenv("ROUTER_RULES_JSON")
    rules_path = os.getenv("ROUTER_RULES_PATH")
    data: Dict[str, Any] = {}
    try:
        if rules_json:
            data = json.loads(rules_json)
        elif rules_path and os.path.isfile(rules_path):
            with open(rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception:
        data = {}
    # normalize structure
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list):
        rules = []
    # coerce fields and provide defaults
    norm_rules: List[Dict[str, Any]] = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        intent = r.get("intent", "qa")
        kw_any = r.get("keywords_any", [])
        priority = r.get("priority", 0)
        try:
            priority = int(priority)
        except Exception:
            priority = 0
        if isinstance(kw_any, str):
            kw_any = [kw_any]
        kw_any = [str(s).lower() for s in kw_any if str(s).strip()]
        norm_rules.append(
            {"intent": intent, "keywords_any": kw_any, "priority": priority}
        )
    # sort by priority desc
    norm_rules.sort(key=lambda r: r.get("priority", 0), reverse=True)
    default_intent = (
        data.get("default_intent", "qa") if isinstance(data, dict) else "qa"
    )
    _RULES_CACHE = {"rules": norm_rules, "default_intent": default_intent}
    return _RULES_CACHE


def _route_by_rules(question: str, grounded: bool) -> tuple[Intent | None, bool]:
    # Grounded queries are always QA
    if grounded:
        return "qa", True  # type: ignore[return-value]
    q = (question or "").lower()
    cfg = _load_rules()
    rules = cfg.get("rules", [])
    matched = None
    for r in rules:
        kws = r.get("keywords_any", [])
        if any(k in q for k in kws):
            matched = r.get("intent", "qa")
            break
    if matched is not None:
        return matched, True  # type: ignore[return-value]
    # No match: if there are rules configured, return default; caller may still choose to fallback
    default_intent = cfg.get("default_intent", "qa")
    return (default_intent, bool(rules))  # type: ignore[return-value]


def _route_builtin(question: str, grounded: bool) -> Intent:
    q = (question or "").lower()
    if grounded:
        return "qa"  # type: ignore[return-value]
    if any(
        t in q
        for t in (
            "pii",
            "email",
            "ssn",
            "social security",
            "credit card",
            "iban",
            "ipv4",
            "ipv6",
            "passport",
            "phone number",
        )
    ):
        if any(w in q for w in ("redact", "mask", "anonymiz", "remediat")):
            return "pii_remediation"  # type: ignore[return-value]
        return "pii_detect"  # type: ignore[return-value]
    if any(
        t in q
        for t in (
            "risk",
            "severity",
            "score",
            "risk score",
            "impact",
            "hazard",
            "danger",
        )
    ):
        return "risk_score"  # type: ignore[return-value]
    if any(
        t in q
        for t in ("policy", "regulation", "regulatory", "compliance", "gdpr", "hipaa")
    ):
        return "policy_navigator"  # type: ignore[return-value]
    return "qa"  # type: ignore[return-value]


def route_intent(question: str, grounded: bool) -> Intent:
    """Classify question as QA, PII detection, risk scoring, policy navigation, or remediation.

    Uses ROUTER_BACKEND (rules or builtin); grounded queries always map to QA.
    """
    backend = os.getenv("ROUTER_BACKEND", _BACKEND_NAME).lower()
    try:
        if backend == "rules":
            intent, had_rules = _route_by_rules(question, grounded)
            # If there were no rules configured or no strong match, fallback to builtin heuristics
            if not had_rules:
                return _route_builtin(question, grounded)
            # If intent is default but builtin would pick a stronger intent (e.g., pii), prefer builtin
            builtin_intent = _route_builtin(question, grounded)
            if intent == "qa" and builtin_intent != "qa":
                return builtin_intent
            return intent  # type: ignore[return-value]
    except Exception:
        pass
    # fallback to builtin
    return _route_builtin(question, grounded)


def get_backend_meta() -> str:
    """Return router backend name and version."""
    return f"{_BACKEND_NAME}_{_BACKEND_VERSION}"
