"""PII remediation synthesis: per-type policies and optional doc-grounded guidance."""
import os
from typing import Any, Dict, List

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _default_remediations() -> Dict[str, Dict[str, Any]]:
    return {
        "email": {
            "action": "mask",
            "pattern": "(?<=.).(?=[^@]*?@)",
            "replacement": "*",
        },
        "phone": {"action": "mask", "pattern": "\d", "replacement": "X"},
        "ssn": {"action": "mask", "pattern": "\d(?!\d{0,3}$)", "replacement": "*"},
        "ipv4": {"action": "mask", "pattern": "\d+", "replacement": "X"},
        "ipv6": {"action": "mask", "pattern": "[0-9a-fA-F]", "replacement": "X"},
        "credit_card": {
            "action": "mask",
            "pattern": "\d(?!\d{0,3}$)",
            "replacement": "*",
        },
        "iban": {"action": "mask", "pattern": "\w(?!\w{0,4}$)", "replacement": "*"},
        "passport": {"action": "mask", "pattern": "\w(?!\w{0,3}$)", "replacement": "*"},
    }


def _snippet_for_type(t: str) -> str:
    snippets = {
        "email": "re.sub(r'(?<=.).(?=[^@]*?@)', '*', value)",
        "phone": "re.sub(r'\\d', 'X', value)",
        "ssn": "re.sub(r'\\d(?!\\d{0,3}$)', '*', value)",
        "credit_card": "re.sub(r'\\d(?!\\d{0,3}$)', '*', value)",
    }
    return snippets.get(t, "# no snippet available for this type")


def _retrieve_guidance(query: str, k: int = 2) -> List[Dict[str, Any]]:
    # provider preserved for future selection; no-op for now to avoid unused warning
    os.getenv("EMBEDDINGS_PROVIDER", os.getenv("LLM_PROVIDER", "local"))
    try:
        from app.services.doc_retriever import answer_with_citations

        resp = answer_with_citations(query, k=k)
        return resp.get("citations", [])
    except Exception:
        return []


def synthesize_remediation(
    entities: List[Dict[str, Any]], include_snippets: bool, grounded: bool
) -> Dict[str, Any]:
    """Build per-type remediation policies; optionally retrieve doc-grounded guidance."""
    remediations = _default_remediations()
    per_type: Dict[str, Dict[str, Any]] = {}
    citations: List[Dict[str, Any]] = []

    for e in entities:
        t = e.get("type")
        if not t:
            continue
        if t not in per_type:
            rule = remediations.get(t, {"action": "mask"})
            entry: Dict[str, Any] = {"type": t, "action": rule.get("action", "mask")}
            # add a simple description
            entry["description"] = (
                f"Apply {entry['action']} to {t} using policy-compliant patterns."
            )
            if include_snippets:
                entry["snippet"] = _snippet_for_type(t)
            per_type[t] = entry
        # We could aggregate examples/positions here if available

    if grounded:
        # Fetch guidance per type
        for t in per_type.keys():
            q = f"Remediation policy for {t} data: masking and handling best practices"
            cites = _retrieve_guidance(q, k=2)
            citations.extend(cites)

    return {"remediation": list(per_type.values()), "citations": citations}
