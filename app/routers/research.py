"""Research endpoints: multi-step agent loop (search, fetch, summarize, risk_check)."""

import os
import time
from typing import List

from fastapi import APIRouter, HTTPException, Request

from app.schemas.research import AgentStep, Finding, ResearchRequest, ResearchResponse
from app.services.agent import Agent
from app.utils.audit import make_hash, write_audit
from app.utils.cost import estimate_tokens_and_cost
from app.utils.rbac import is_allowed_agent_step, parse_role
from db.session import get_session, init_db

router = APIRouter()


@router.post("/research", response_model=ResearchResponse)
def post_research(req: Request, payload: ResearchRequest):
    """Run multi-step research agent with guest/analyst/admin role-based restrictions.

    Steps: search, fetch, summarize, risk_check. Guests cannot use fetch step.
    Audit includes step hashes and overall latency."""
    start = time.perf_counter()

    if not payload.topic or len(payload.topic.strip()) < 3:
        raise HTTPException(status_code=400, detail="topic too short")

    steps = payload.steps or ["search", "fetch", "summarize", "risk_check"]
    for s in steps:
        if s not in ["search", "fetch", "summarize", "risk_check"]:
            raise HTTPException(status_code=400, detail=f"unsupported step: {s}")

    # RBAC step policy: guests cannot use 'fetch'
    role = parse_role(req)
    for s in steps:
        if not is_allowed_agent_step(role, s):
            raise HTTPException(
                status_code=403, detail=f"step '{s}' not allowed for this role"
            )

    agent = Agent()
    findings, sources, audit_steps, flagged = agent.run(payload.topic, steps)

    # Token & cost (very rough)
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    text_out = "\n".join([f.get("summary", "") for f in findings])
    tp, tc, cost = estimate_tokens_and_cost(
        model=model, prompt=payload.topic, completion=text_out
    )

    latency_ms = int((time.perf_counter() - start) * 1000)

    # Prompt registry (non-disruptive): record prompt name/version in audit
    from app.utils.prompts import load_prompt

    prompt_name = "research"
    prompt_version_env = os.getenv("PROMPT_RESEARCH_VERSION")
    try:
        loaded = load_prompt(prompt_name, version=prompt_version_env)
        prompt_version = f"{prompt_name}:{loaded.get('version')}"
    except Exception:
        prompt_version = f"{prompt_name}:unknown"

    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "user_id": payload.user_id,
        "endpoint": "/research",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tokens_prompt": tp,
        "tokens_completion": tc,
        "cost_usd": round(cost, 6),
        "latency_ms": latency_ms,
        "compliance_flag": bool(flagged),
        "prompt_hash": make_hash(payload.topic),
        "response_hash": make_hash(text_out),
        "prompt_version": prompt_version,
    }

    # Persist audit row
    try:
        init_db()
    except Exception:
        pass
    db = get_session()
    try:
        write_audit(
            db,
            request_id=audit["request_id"],
            endpoint=audit["endpoint"],
            user_id=audit["user_id"],
            tokens_prompt=audit["tokens_prompt"],
            tokens_completion=audit["tokens_completion"],
            cost_usd=audit["cost_usd"],
            latency_ms=audit["latency_ms"],
            compliance_flag=audit["compliance_flag"],
            prompt_hash=audit["prompt_hash"],
            response_hash=audit["response_hash"],
        )
    finally:
        db.close()

    # Build response models
    out_findings: List[Finding] = [Finding(**f) for f in findings]
    out_steps: List[AgentStep] = [AgentStep(**s) for s in audit_steps]

    return ResearchResponse(
        findings=out_findings, sources=sources, steps=out_steps, audit=audit
    )
