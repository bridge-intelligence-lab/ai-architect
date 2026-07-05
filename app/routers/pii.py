"""PII detection endpoints: identify sensitive data in text."""

import os
import time
from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.services.pii_detector import detect_pii
from app.utils.audit import make_hash, write_audit
from app.utils.cost import estimate_tokens_and_cost
from app.utils.rbac import parse_role

router = APIRouter()


class PiiRequest(BaseModel):
    text: str = Field(min_length=1)
    types: Optional[List[str]] = None
    grounded: bool = False


class PiiResponse(BaseModel):
    summary: str
    entities: List[dict]
    counts: dict
    types_present: List[str]
    audit: dict


@router.post("/pii", response_model=PiiResponse)
def post_pii(req: Request, payload: PiiRequest):
    """Detect PII types in text and return counts by entity type.

    Requires analyst role. Optional grounded citations from policy docs."""
    # RBAC: analyst/admin (minimum analyst)
    # Use dependency function style but we call it here for simplicity
    # If role < analyst, raise 403
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    start = time.perf_counter()
    # Detect
    result = detect_pii(payload.text, types=payload.types)
    if result.get("total", 0) > 0:
        parts = [f"{k}({v})" for k, v in sorted(result.get("counts", {}).items())]
        summary = ", ".join(parts)
        answer = f"Detected PII: {summary}."
    else:
        answer = "No PII detected."

    # Optional RAG citations for policy references
    if payload.grounded:
        try:
            from app.services.doc_retriever import answer_with_citations

            resp = answer_with_citations("PII policy references", k=3)
            _ = resp.get("citations", [])
        except Exception:
            pass

    # Cost/tokens
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    tp, tc, cost = estimate_tokens_and_cost(
        model=model, prompt=payload.text, completion=answer
    )

    latency_ms = int((time.perf_counter() - start) * 1000)

    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/pii",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tokens_prompt": tp,
        "tokens_completion": tc,
        "cost_usd": round(cost, 6),
        "latency_ms": latency_ms,
        "prompt_hash": make_hash(payload.text),
        "response_hash": make_hash(answer),
        "pii_entities_count": result.get("total", 0),
        "pii_types": result.get("types_present", []),
        "pii_counts": result.get("counts", {}),
    }

    # Persist audit
    try:
        from db.session import get_session, init_db

        init_db()
        db = get_session()
        try:
            write_audit(
                db,
                request_id=audit.get("request_id"),
                endpoint=audit.get("endpoint"),
                user_id=None,
                tokens_prompt=audit.get("tokens_prompt"),
                tokens_completion=audit.get("tokens_completion"),
                cost_usd=audit.get("cost_usd"),
                latency_ms=audit.get("latency_ms"),
                compliance_flag=False,
                prompt_hash=audit.get("prompt_hash"),
                response_hash=audit.get("response_hash"),
            )
        finally:
            db.close()
    except Exception:
        pass

    return PiiResponse(
        summary=answer,
        entities=result["entities"],
        counts=result["counts"],
        types_present=result["types_present"],
        audit=audit,
    )
