"""Risk scoring endpoints: heuristic risk assessment of text."""

import os
import time

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.risk_scorer import score
from app.utils.audit import make_hash, write_audit
from app.utils.cost import estimate_tokens_and_cost
from app.utils.rbac import parse_role

router = APIRouter()


class RiskRequest(BaseModel):
    text: str = Field(min_length=1)


class RiskResponse(BaseModel):
    label: str
    value: float
    rationale: str
    audit: dict


@router.post("/risk", response_model=RiskResponse)
def post_risk(req: Request, payload: RiskRequest):
    """Score text for risk (low/medium/high) with rationale and scoring method.

    Requires analyst role."""
    # RBAC: analyst/admin
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    start = time.perf_counter()
    result = score(payload.text)

    answer = f"Risk: {result['label']} ({result['value']:.2f})."

    # Tokens/cost (stub)
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    tp, tc, cost = estimate_tokens_and_cost(
        model=model, prompt=payload.text, completion=answer
    )

    latency_ms = int((time.perf_counter() - start) * 1000)
    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/risk",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tokens_prompt": tp,
        "tokens_completion": tc,
        "cost_usd": round(cost, 6),
        "latency_ms": latency_ms,
        "prompt_hash": make_hash(payload.text),
        "response_hash": make_hash(answer),
        "risk_score_label": result["label"],
        "risk_score_value": result["value"],
        "risk_score_method": result.get("method", "heuristic"),
    }

    # Persist audit (best-effort)
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

    return RiskResponse(
        label=result["label"],
        value=result["value"],
        rationale=result["rationale"],
        audit=audit,
    )
