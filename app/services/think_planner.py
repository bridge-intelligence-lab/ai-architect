import os
from typing import Any, Dict, Tuple

from app.services.architect_agent import run_architect_agent


async def handle_think_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route ThinkRequest/ToolResult to the planner and return actions or a plan.
    - For ThinkRequest: use run_architect_agent to produce a plan and optional next action.
    - For ToolResult: incorporate tool feedback (stub P1), then produce next steps.
    """
    req_type = payload.get("request_type")
    session_id = payload.get("session_id")
    user_id = payload.get("user_id")

    if req_type == "ThinkRequest":
        question = payload.get("prompt", "").strip()
        llm_model = os.getenv("LLM_MODEL")
        plan, audit = run_architect_agent(question, session_id=session_id, user_id=user_id, llm_model=llm_model)
        # P1: return a plan; tools can be introduced by prompts later
        return {"plan": plan.model_dump() if hasattr(plan, "model_dump") else dict(plan)}

    if req_type == "ToolResult":
        # For P1, just acknowledge and ask for next plan step (no true tool state update yet)
        tool_summary = f"ToolResult received for {payload.get('correlation_id')}."
        question = f"Continue planning based on tool feedback: {tool_summary}"
        llm_model = os.getenv("LLM_MODEL")
        plan, audit = run_architect_agent(question, session_id=session_id, user_id=user_id, llm_model=llm_model)
        return {"plan": plan.model_dump() if hasattr(plan, "model_dump") else dict(plan)}

    raise ValueError("Unsupported request_type")
