# Architect Deterministic Mode (LangGraph)

> **Historical proposal — superseded.** LangGraph shipped as a different
> design: an opt-in tool-loop agent behind `AGENT_BACKEND=langgraph` (see
> docs/agents.md and ADR-0007), not the concurrent-pipeline mode described
> here. The `/architect/final` endpoint proposed below was never built. Kept
> for design history.

Problem
- Current SSE streaming delivers partial content (summary, steps, flags, citations) as events arrive. It can feel disjointed and requires UI tricks (typing, buffering) to appear coherent.
- We want a mode that executes sub-tasks concurrently but returns a single cohesive deliverable at the end.

Proposal
- Add a LangGraph (LCEL/LangGraph-style) pipeline for the Architect that orchestrates sub-tasks asynchronously with typed node contracts and per-node audit. The API returns one final, consolidated response after all branches complete.

Goals
- Concurrency for retrieval and planning, but a single final deliverable.
- Deterministic orchestration with retries and explicit error edges.
- Strong observability per node (latency, inputs/outputs preview, citations size, tokens/cost).
- Clean UX: progress indicators during execution, one cohesive plan on completion.

Suggested Graph Nodes
- input
  - Inputs: question, session_id, user_id, grounded hint (optional)
  - Outputs: normalized question, config flags (env), role context
- rag_retrieval
  - Inputs: normalized question, RAG flags (multi-query, hyDE)
  - Work: query docs via LangChain RAG; returns citations, rag flags
  - Outputs: citations[], rag_meta
- plan_generation
  - Inputs: question, citations (optional)
  - Work: single LLM call producing ArchitectPlan (summary, steps?, flags?, tone_hint?, feature_request?)
  - Outputs: plan fields + llm meta
- feature_detection
  - Inputs: plan
  - Work: heuristic to set suggest_feature + feature_request
  - Outputs: updated plan fields
- audit_enrichment
  - Inputs: rag_meta, llm meta, request meta
  - Work: merge audit fields (tokens, cost, grounded_used, rag flags)
  - Outputs: audit

Edges and Concurrency
- input → rag_retrieval (async)
- input → plan_generation (async)
- rag_retrieval + plan_generation → feature_detection
- rag_retrieval + plan_generation → audit_enrichment

Final Assembly
- Once all nodes finish, return a single JSON object:
  - summary (required, concise)
  - steps (optional; no defaults)
  - flags (optional)
  - citations (compact list)
  - feature (optional CTA)
  - audit (meta and costs)

API
- New endpoint: POST /architect/final
  - Request: { question, session_id?, user_id?, grounded? }
  - Response: { summary, steps?, flags?, citations?, feature?, audit }
- Optional progress endpoint or SSE (minimal):
  - Emit node_started/node_done events; UI shows milestones (Retrieving, Planning, Finalizing).

UI
- Mode toggle: Stream (current SSE) vs Deterministic (final deliverable).
- Deterministic mode behavior:
  - Show progress milestones.
  - On completion, render a single plan bubble with summary (top) then steps (if present), flags, citations.
  - Citations compact with Show/Hide toggle.

Observability and Testing
- Per-node logging/metrics: duration, retries, errors; artifacts previews.
- Unit tests per node; integration tests for graph success and failure edges.
- Audit row persists final status and key flags (rag_multi_query, rag_hyde, grounded_used).

Rollout Plan
- Phase 1: Implement backend graph with minimal UI (progress text).
- Phase 2: Enhance UI/UX; add toggles and compact citations.
- Phase 3: Retries/timeouts and resilience (fallbacks); richer tests and docs.

Notes
- Keep current SSE streaming mode for exploratory, chat-like usage.
- Deterministic mode offers production-friendly, coherent responses with clear execution semantics.
