import os
from typing import AsyncGenerator, Dict, Any
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.services.architect_agent import run_architect_agent

router = APIRouter()

async def _gen_sse(plan: Dict[str, Any], audit: Dict[str, Any]) -> AsyncGenerator[bytes, None]:
    import json
    # Emit meta first (include memory stats when present)
    meta = {
        "provider": audit.get("llm_provider"),
        "model": audit.get("llm_model"),
        "grounded_used": plan.get("grounded_used"),
    }
    # Include memory keys consistently when flags are enabled
    def _flag_on(name: str) -> bool:
        return (os.getenv(name, "false").lower() in ("1","true","yes","on"))
    if _flag_on("MEMORY_SHORT_ENABLED"):
        meta["memory_short_reads"] = int(audit.get("memory_short_reads", 0) or 0)
    if _flag_on("MEMORY_LONG_ENABLED"):
        meta["memory_long_reads"] = int(audit.get("memory_long_reads", 0) or 0)
    yield f"event: meta\ndata: {json.dumps(meta)}\n\n".encode()
    # Summary
    if plan.get("summary"):
        yield f"event: summary\ndata: {json.dumps(plan.get('summary'))}\n\n".encode()
    # Steps
    if plan.get("suggested_steps"):
        yield f"event: steps\ndata: {json.dumps(plan.get('suggested_steps'))}\n\n".encode()
    # Flags
    if plan.get("suggested_env_flags"):
        yield f"event: flags\ndata: {json.dumps(plan.get('suggested_env_flags'))}\n\n".encode()
    # Citations
    if plan.get("citations"):
        yield f"event: citations\ndata: {json.dumps(plan.get('citations'))}\n\n".encode()
    # Feature request
    fr = plan.get("feature_request")
    if plan.get("suggest_feature") and fr:
        yield f"event: feature\ndata: {json.dumps(fr)}\n\n".encode()
    # Final audit
    yield f"event: audit\ndata: {json.dumps(audit)}\n\n".encode()

@router.get(
    "/architect/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "text/event-stream": {"schema": {"type": "string"}},
            }
        }
    },
)
async def stream_architect(request: Request, question: str | None = None, session_id: str | None = None, user_id: str | None = None, llm_model: str | None = None):
    # Defensive guard: no-op stream for empty/short questions
    q = (question or "").strip()
    if len(q) < 3:
        async def _empty():
            yield b"event: meta\ndata: {}\n\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    # Run the agent inside the generator so the client gets an immediate
    # status event instead of a silent connection for the whole agent run.
    async def _run() -> AsyncGenerator[bytes, None]:
        import json

        yield b'event: status\ndata: "planning"\n\n'
        try:
            plan_obj, audit = await run_in_threadpool(
                run_architect_agent, q, session_id, user_id, llm_model
            )
        except Exception as e:
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n".encode()
            return
        plan: Dict[str, Any] = plan_obj.model_dump() if hasattr(plan_obj, "model_dump") else dict(plan_obj)
        async for chunk in _gen_sse(plan, audit):
            yield chunk

    return StreamingResponse(_run(), media_type="text/event-stream")
