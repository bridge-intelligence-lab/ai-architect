"""PII remediation endpoints: generate redaction/anonymization guidance."""

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.utils.rbac import parse_role

router = APIRouter()


class PiiRemediationRequest(BaseModel):
    text: str = Field(min_length=3)
    return_snippets: Optional[bool] = True
    grounded: Optional[bool] = False


class PiiRemediationResponse(BaseModel):
    remediation: List[Dict[str, Any]]
    citations: List[Dict[str, Any]] = []
    audit: dict


@router.post("/pii_remediation", response_model=PiiRemediationResponse)
def post_pii_remediation(req: Request, payload: PiiRemediationRequest):
    """Synthesize remediation steps for detected PII with optional code snippets.

    Requires analyst role. Gated by PII_REMEDIATION_ENABLED flag (default true)."""
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=403, detail="forbidden")
    if os.getenv("PII_REMEDIATION_ENABLED", "true").lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        raise HTTPException(status_code=503, detail="pii remediation disabled")

    # detect PII
    try:
        from app.services.pii_detector import detect_pii

        result = detect_pii(payload.text)
        entities = result.get("entities", [])
    except Exception:
        entities = []

    # synthesize remediation
    try:
        from app.services.pii_remediation import synthesize_remediation

        out = synthesize_remediation(
            entities,
            include_snippets=bool(payload.return_snippets),
            grounded=bool(payload.grounded),
        )
    except Exception:
        out = {"remediation": [], "citations": []}

    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/pii_remediation",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pii_entities_count": len(entities),
        "pii_types": sorted(list({e.get("type") for e in entities if e.get("type")})),
    }

    return PiiRemediationResponse(
        remediation=out.get("remediation", []),
        citations=out.get("citations", []),
        audit=audit,
    )
