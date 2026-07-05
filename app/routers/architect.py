"""Architect endpoints: structured plan generation (POST) and HTML UI."""

import os
import time
from pathlib import Path
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.routers.query import Citation
from app.services.doc_retriever import answer_with_citations
from app.services.architect_agent import run_architect_agent
from app.utils.rbac import is_allowed_grounded_query, parse_role
from app.utils.prompts import load_prompt
from app.utils.audit import make_hash, write_audit
from db.session import get_session

router = APIRouter()


class ArchitectRequest(BaseModel):
    question: str = Field(..., min_length=3)
    grounded: Optional[bool] = Field(None, description="force retrieval from docs; when None, decide dynamically")
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ArchitectResponse(BaseModel):
    answer: str
    citations: List[Citation] = []
    suggested_steps: List[str] = []
    suggested_env_flags: List[str] = []
    audit: Dict[str, Any]
    suggest_feature: Optional[bool] = None
    feature_request: Optional[Dict[str, Any]] = None


@router.post("/architect", response_model=ArchitectResponse, tags=["Architect"])
def post_architect(request: Request, payload: ArchitectRequest):
    """Generate structured plan from question with optional grounded retrieval.

    Requires PROJECT_GUIDE_ENABLED flag. Optional LLM synthesis when LLM_ENABLE_ARCHITECT=true.
    Audit includes prompt/response hashes and LLM usage when agent runs."""
    # feature flag guard
    if os.getenv("PROJECT_GUIDE_ENABLED", "").lower() not in ("1", "true", "yes", "on"):
        raise HTTPException(status_code=404, detail="Architect mode not enabled")

    role = parse_role(request)

    # Decide grounded dynamically when not provided
    if payload.grounded is None:
        # Simple heuristic: treat design/setup/config questions as grounded candidates
        lower_q = (payload.question or "").lower()
        payload.grounded = any(w in lower_q for w in ("gdpr", "policy", "config", "setup", "flag", "env", "compliance", "docs"))
    else:
        payload.grounded = bool(payload.grounded)

    # load prompt metadata for auditing
    prompt_name = "project_guide"
    try:
        prompt_meta = load_prompt(prompt_name)
        prompt_ver = f"{prompt_name}:{prompt_meta['version']}"
    except Exception:
        prompt_ver = f"{prompt_name}:unknown"

    # RAG stage (only when grounded)
    citations: List[Citation] = []
    rag_meta: Dict[str, Any] = {}
    if payload.grounded:
        docs_path = os.getenv("DOCS_PATH") or "./docs"
        os.environ["DOCS_PATH"] = docs_path
        result = answer_with_citations(payload.question, k=3)
        citations = [Citation(**c) for c in result.get("citations", [])]
        for k in ("rag_multi_query", "rag_multi_count", "rag_hyde"):
            if k in result:
                rag_meta[k] = result[k]

    # Optionally run LLM prompts for Architect (via structured Architect Agent)
    llm_enabled = os.getenv("LLM_ENABLE_ARCHITECT", "false").lower() in ("1", "true", "yes", "on")

    # Initialize defaults
    steps: List[str] = []
    flags: List[str] = []
    summary: str = ""
    llm_provider = None
    llm_model = None
    llm_tokens_prompt = None
    llm_tokens_completion = None
    llm_cost_usd = None

    plan = None
    agent_audit: Dict[str, Any] = {}

    if llm_enabled:
        try:
            plan, agent_audit = run_architect_agent(payload.question, session_id=payload.session_id, user_id=payload.user_id)
            # Map fields
            steps = list(plan.suggested_steps or [])
            flags = list(plan.suggested_env_flags or [])
            summary = str(getattr(plan, "summary", "") or "")
            # Feature request passthrough (optional polish)
            suggest_feature = getattr(plan, "suggest_feature", None)
            feature_request = getattr(plan, "feature_request", None)
            # LLM audit fields
            llm_provider = agent_audit.get("llm_provider")
            llm_model = agent_audit.get("llm_model")
            llm_tokens_prompt = agent_audit.get("llm_tokens_prompt")
            llm_tokens_completion = agent_audit.get("llm_tokens_completion")
            llm_cost_usd = agent_audit.get("llm_cost_usd")
            # If grounded used inside agent, prefer agent-provided citations
            if getattr(plan, "grounded_used", False) and getattr(plan, "citations", None):
                citations = [Citation(**c) for c in plan.citations]
        except Exception:
            # keep defaults and allow deterministic fallbacks below
            pass
    else:
        steps, flags, summary = [], [], ""

    # Deterministic fallback or completion of missing fields
    # Dynamic completion of missing fields
    if not summary:
        summary = (
            f"Found {len(citations)} citations; see references below." if citations else "No direct citations found; here's an overview."
        )
    if not steps:
        router_files = [
            f.stem
            for f in Path("app/routers").glob("*.py")
            if f.name not in ("__init__.py", "architect.py")
        ]
        steps = steps or [
            "Map your business use case to existing endpoints/services:",
            *[f"  •  /{name.replace('_router', '')}" for name in router_files],
            "Outline components to customize, flags to toggle, and files to update.",
        ]
    if not flags:
        flags = flags or [
            "PROJECT_GUIDE_ENABLED",
            "RAG_MULTI_QUERY_ENABLED",
            "RAG_MULTI_QUERY_COUNT",
            "RAG_HYDE_ENABLED",
        ]


    # Normalize to always-present list/string types for response keys
    if not isinstance(steps, list):
        steps = []
    if not isinstance(flags, list):
        flags = []
    if not isinstance(summary, str):
        summary = str(summary) if summary is not None else ""

    answer = "\n\n".join(
        [
            f"**Summary**\n{summary}",
            "**Steps**\n" + "\n".join(f"- {s}" for s in steps),
            "**Relevant Env Flags**\n" + ", ".join(flags),
        ]
    )

    start = time.perf_counter()
    audit = {
        "request_id": getattr(request.state, "request_id", None),
        "user_id": payload.user_id,
        "endpoint": "/architect",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prompt_hash": make_hash(payload.question),
        "response_hash": make_hash(answer),
        "prompt_version": prompt_ver,
        **rag_meta,
        **(agent_audit or {}),
    }
    # LLM audit fields when present
    if 'llm_provider' in locals() and llm_provider:
        audit["llm_provider"] = llm_provider
    if 'llm_model' in locals() and llm_model:
        audit["llm_model"] = llm_model
    if 'llm_tokens_prompt' in locals() and llm_tokens_prompt is not None:
        audit["llm_tokens_prompt"] = int(llm_tokens_prompt or 0)
    if 'llm_tokens_completion' in locals() and llm_tokens_completion is not None:
        audit["llm_tokens_completion"] = int(llm_tokens_completion or 0)
    if 'llm_cost_usd' in locals() and llm_cost_usd is not None:
        try:
            audit["llm_cost_usd"] = float(llm_cost_usd)
        except Exception:
            pass
    latency_ms = int((time.perf_counter() - start) * 1000)
    audit["latency_ms"] = latency_ms

    db = get_session()
    try:
        write_audit(
            db,
            request_id=audit["request_id"],
            endpoint=audit["endpoint"],
            user_id=audit["user_id"],
            tokens_prompt=None,
            tokens_completion=None,
            cost_usd=None,
            latency_ms=latency_ms,
            compliance_flag=False,
        )
    finally:
        db.close()

    # Ensure llm audit fields exposed in response when present (already merged, keep for safety)
    for k in ("llm_provider", "llm_model", "llm_tokens_prompt", "llm_tokens_completion", "llm_cost_usd"):
        v = locals().get(k)
        if v is not None:
            audit[k] = v

    # Filter memory fields from audit when memory is disabled
    def _flag_on(name: str) -> bool:
        return os.getenv(name, "false").lower() in ("1", "true", "yes", "on")

    short_on = _flag_on("MEMORY_SHORT_ENABLED")
    long_on = _flag_on("MEMORY_LONG_ENABLED")
    if audit:
        filtered = {}
        for k, v in audit.items():
            if k.startswith("memory_short_") and not short_on:
                continue
            if k.startswith("memory_long_") and not long_on:
                continue
            if k == "summary_updated" and not short_on:
                continue
            filtered[k] = v
        audit = filtered

    return ArchitectResponse(
        answer=answer,
        citations=citations,
        suggested_steps=steps,
        suggested_env_flags=flags,
        audit=audit,
        suggest_feature=locals().get('suggest_feature'),
        feature_request=locals().get('feature_request'),
    )
