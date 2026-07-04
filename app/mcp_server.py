"""MCP server exposing AI-Architect capabilities over the Model Context Protocol.

Run over stdio (for Claude Desktop / Claude Code / any MCP client):

    python -m app.mcp_server

Tools map onto the same service layer the HTTP API uses, so backend flags
apply unchanged: RAG_BACKEND selects keyword scan vs Chroma vector
retrieval, AGENT_BACKEND selects the builtin planner vs the LangGraph
tool-loop agent, and LLM_PROVIDER=stub keeps everything offline.
"""

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "ai-architect",
    instructions=(
        "AI-Architect reference platform: grounded document retrieval, "
        "PII detection, and an architecture-planning agent with audit "
        "metadata (tokens, cost, backends)."
    ),
)


@mcp.tool()
def retrieve_docs(query: str, k: int = 3) -> Dict[str, Any]:
    """Retrieve documentation citations for a query.

    Uses the configured retrieval backend (RAG_BACKEND: keyword_scan or
    vector) and returns an extractive answer plus source citations.
    """
    from app.services.doc_retriever import answer_with_citations

    return answer_with_citations(query, k=k)


@mcp.tool()
def detect_pii(text: str, types: Optional[List[str]] = None) -> Dict[str, Any]:
    """Detect PII entities (emails, phones, ids, ...) in the given text."""
    from app.services.pii_detector import detect_pii as _detect

    return _detect(text, types=types)


@mcp.tool()
def architect_plan(question: str) -> Dict[str, Any]:
    """Produce an architecture plan for the question.

    Runs the architect agent (AGENT_BACKEND: builtin planner or LangGraph
    tool-loop) and returns the plan plus audit metadata including
    agent_backend, token counts, and real cost_usd.
    """
    from app.services.architect_agent import run_architect_agent

    plan, audit = run_architect_agent(question)
    return {"plan": plan.model_dump(), "audit": audit}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
