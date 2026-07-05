---
title: ADR 0008: Expose architect capabilities over MCP
status: current
module: architecture
last_reviewed: 2026-07-05
decision_date: 2026-07-04
adr_status: Accepted
---

# ADR 0008: Expose architect capabilities over MCP

## Context

- ADR-0004 identified MCP as the connective tissue of the 2026 agent
  ecosystem and the highest-signal gap in this repo: every capability was
  reachable only through the bespoke HTTP API, so agent hosts (Claude
  Desktop/Code, MCP-aware IDEs, other agent runtimes) could not consume it
  without custom glue.
- The service layer is already cleanly separated from the routers
  (doc_retriever, pii_detector, architect_agent), so an MCP surface can sit
  beside FastAPI without touching request handling.

## Decision

- Add `app/mcp_server.py` using the official `mcp` SDK's FastMCP, run over
  stdio via the `ai-architect-mcp` console script (or
  `python -m app.mcp_server`).
- Expose three tools mapping 1:1 onto the service layer: `retrieve_docs`
  (doc_retriever, so `RAG_BACKEND` keyword/vector applies), `detect_pii`,
  and `architect_plan` (run_architect_agent, so `AGENT_BACKEND`
  builtin/langgraph applies and the audit with agent_backend, tokens, and
  real cost_usd rides along in the tool result).
- Buy-over-build: the SDK owns transport, protocol negotiation, and schema
  generation from type hints; the repo contributes only the tool bodies.
- Tests use the SDK's in-memory connected client/server session, so the
  full MCP round-trip (list_tools, call_tool, error surfacing) is covered
  offline with no subprocess.

## Consequences

- Any MCP client can now call the platform's governed capabilities; audit
  metadata travels with results, keeping the FinOps/observability story
  intact outside HTTP.
- New dependency `mcp>=1.20.0` (verified against 1.28.1).
- RBAC is not enforced on the MCP surface in this iteration: stdio servers
  inherit the trust of the host process. Role-scoped MCP (e.g. via an
  authenticated HTTP transport) is follow-up work if the surface is ever
  exposed beyond the local host.
