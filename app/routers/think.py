import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.utils.rbac import parse_role
from app.utils.cost import estimate_tokens_and_cost
from app.services.think_planner import handle_think_request

router = APIRouter()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@router.post("/think")
async def think_endpoint(req: Request, payload: Dict[str, Any]):
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    start = time.perf_counter()

    request_type = payload.get("request_type")
    if request_type not in ("ThinkRequest", "ToolResult"):
        raise HTTPException(status_code=400, detail="invalid request_type")

    try:
        response = await handle_think_request(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"think failed: {e}")

    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
    tp, tc, cost = estimate_tokens_and_cost(
        model=model_name, prompt=str(payload), completion=str(response)
    )

    latency_ms = int((time.perf_counter() - start) * 1000)
    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/think",
        "created_at": _now_iso(),
        "tokens_prompt": tp,
        "tokens_completion": tc,
        "cost_usd": cost,
        "latency_ms": latency_ms,
    }

    if isinstance(response, dict):
        response.setdefault("audit", {}).update(audit)
    else:
        response = {"plan": response, "audit": audit}

    return response
