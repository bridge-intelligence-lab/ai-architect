"""MCP server: tools exposed over a real in-memory MCP client session."""

import json

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from app.mcp_server import mcp


def _run(coro_fn):
    return anyio.run(coro_fn)


def test_mcp_lists_expected_tools():
    async def _t():
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as client:
            tools = await client.list_tools()
            return sorted(t.name for t in tools.tools)

    names = _run(_t)
    assert names == ["architect_plan", "detect_pii", "retrieve_docs"]


def test_mcp_retrieve_docs_returns_citations(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gdpr.txt").write_text("GDPR governs data protection in the EU.")
    monkeypatch.setenv("DOCS_PATH", str(docs))
    monkeypatch.delenv("RAG_BACKEND", raising=False)

    async def _t():
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as client:
            res = await client.call_tool(
                "retrieve_docs", {"query": "GDPR data protection", "k": 2}
            )
            return json.loads(res.content[0].text)

    out = _run(_t)
    assert out["rag_backend"] == "keyword_scan"
    assert out["citations"]
    assert out["citations"][0]["source"] == "gdpr.txt"
    assert out["answer"].startswith("Extracted from matching documents:")


def test_mcp_detect_pii():
    async def _t():
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as client:
            res = await client.call_tool(
                "detect_pii", {"text": "Contact john@example.com please"}
            )
            return json.loads(res.content[0].text)

    out = _run(_t)
    assert out["total"] >= 1
    assert "email" in {e.get("type") for e in out.get("entities", [])}


def test_mcp_architect_plan_includes_audit(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("AGENT_BACKEND", raising=False)

    async def _t():
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as client:
            res = await client.call_tool(
                "architect_plan", {"question": "How should I add RBAC?"}
            )
            return json.loads(res.content[0].text)

    out = _run(_t)
    assert "plan" in out and "audit" in out
    assert out["audit"]["agent_backend"] == "builtin"
    assert "llm_cost_usd" in out["audit"]


def test_mcp_tool_error_is_reported(monkeypatch):
    # A tool raising inside the server must surface as an MCP tool error,
    # not a transport crash.
    import app.services.pii_detector as pii

    def _boom(*a, **k):
        raise RuntimeError("detector down")

    monkeypatch.setattr(pii, "detect_pii", _boom)

    async def _t():
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as client:
            return await client.call_tool("detect_pii", {"text": "x"})

    res = _run(_t)
    assert res.isError is True


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
