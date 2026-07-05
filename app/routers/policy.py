"""Policy navigator endpoints: decompose and answer compliance questions."""

import os
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services import policy_navigator as policy
from app.utils.audit import make_hash
from app.utils.rbac import parse_role

router = APIRouter()


class PolicyRequest(BaseModel):
    question: str = Field(min_length=3)
    max_subqs: Optional[int] = Field(
        default=None, description="Override max sub-questions"
    )


class PolicyResponse(BaseModel):
    recommendation: str
    citations: List[dict]
    audit: dict


@router.post("/policy_navigator", response_model=PolicyResponse)
def post_policy_navigator(req: Request, payload: PolicyRequest):
    """Answer policy questions via decompose-retrieve-synthesize loop.

    Requires analyst role. Gated by POLICY_NAV_ENABLED flag (default true).
    Audit includes step-by-step latencies and hashes."""
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=403, detail="forbidden")
    if os.getenv("POLICY_NAV_ENABLED", "true").lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        raise HTTPException(status_code=503, detail="policy navigator disabled")

    start = time.perf_counter()

    # decompose
    t0 = time.perf_counter()
    subqs = policy.decompose(payload.question, payload.max_subqs)
    t1 = time.perf_counter()

    # retrieve for each
    per_subq = []
    for sq in subqs:
        per_subq.append(policy.retrieve(sq, k=3))

    # synthesize
    out = policy.synthesize(payload.question, subqs, per_subq)

    duration_ms = int((time.perf_counter() - start) * 1000)

    steps = [
        {
            "name": "decompose",
            "inputs": {"question": payload.question, "max_subqs": payload.max_subqs},
            "outputs_preview": subqs,
            "latency_ms": int((t1 - t0) * 1000),
            "hash": make_hash("|".join(subqs) if subqs else payload.question),
        }
    ]
    for sq, cites in zip(subqs, per_subq):
        steps.append(
            {
                "name": "retrieve",
                "inputs": {"subq": sq},
                "outputs_preview": cites[:2],
                "latency_ms": None,
                "hash": make_hash(sq),
            }
        )
    steps.append(
        {
            "name": "synthesize",
            "inputs": {"subqs": subqs},
            "outputs_preview": out.get("answer", "")[:120],
            "latency_ms": None,
            "hash": make_hash(out.get("answer", "")),
        }
    )

    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/policy_navigator",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "latency_ms": duration_ms,
        "steps": steps,
    }

    return PolicyResponse(
        recommendation=out.get("answer", ""),
        citations=out.get("citations", []),
        audit=audit,
    )
