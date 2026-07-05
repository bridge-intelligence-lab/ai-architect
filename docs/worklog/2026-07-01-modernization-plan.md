# Modernization Plan

This repo was first written in late 2025 while learning the LLM/agent stack. A
lot of capability was hand-rolled rather than pulled from a framework. That was
a deliberate learning choice and, in several places, remains the right call.
This plan records where hand-rolled stays (documented as a build-vs-buy
decision), where a library genuinely earns its place, and sequences the work
into small, reviewable PRs.

See [ADR-0004: Build-vs-buy policy](adr/0004-build-vs-buy.md) for the
per-component rationale, and
[ADR-0001: Ports-and-Adapters](adr/0001-ports-and-adapters.md) for the seam
these changes slot into (real adapters filling existing ports).

## Scope

**ai-architect** is a reference implementation for running LLM and agent
services with production controls: RBAC, audit trails, cost/FinOps metrics,
retrieval, and MLOps, on a FastAPI + ports-and-adapters core. It is
domain-neutral platform infrastructure; domain-specific scenarios live in their
own repos. Multi-agent orchestration enters this repo as working code (PRs F
and G below), not as standalone design docs.

## Principles

- **Docs track code.** A capability is described as shipped only when the code
  does it; everything else is roadmap. The docs PR (A) lands before the
  up-levels so the baseline is accurate.
- **Adopt a library only when the hand-rolled version is worse on a real axis**
  (a reliability liability or an unmet capability), not for fashion.
  Modernizing here mostly *reduces* framework coupling.
- **One short-lived branch per PR off `main`,** merged when CI is green. Each
  PR is independently valuable and revertible.
- **Every PR carries its docs:** an ADR for any decision, updates to the
  relevant `docs/*.md`, and a `CHANGELOG.md` entry.

## Locked decisions

- **Agent (PR F): build a real LangGraph agent.** Shipped: a genuine tool-loop
  agent on LangGraph behind `AGENT_BACKEND=langgraph`, with the deterministic
  planner as the default/offline path (ADR-0007). A measured comparison later
  found langgraph wins on groundedness and latency
  (docs/eval_results/2026-07-04-grid-backend-tokens.md).
- **LangChain (PR D): drop it, keep only `langchain-core`.** Native structured
  outputs remove the need for the heavyweight package; `langchain-core` stays
  only for typed output parsers. This also retires the stale
  `langchain==0.1.11` pin.

## PR sequence

| # | Branch | Scope | Docs | Size | Depends on | Status |
|---|--------|-------|------|------|------------|--------|
| 0 | `ci/health` | Fix MLflow file-store opt-out and regenerate the OpenAPI schema so CI is green for everything after. | testing.md | S | — | ✅ |
| A | `docs/scope-and-roadmap` | Scope statement, roadmap refresh, this plan, build-vs-buy ADR. No code behavior change. | ADR-0004, README | S | — | ✅ |
| B | `refactor/rag-naming` | Rename `langchain_rag.py` → `doc_retriever.py` to match what it does; retire placeholder response paths. | rag.md | S | A | ✅ |
| C | `feat/vector-rag` | Real embeddings (sentence-transformers) + Chroma retrieval behind `RAG_BACKEND`; keep deterministic baseline as fallback; wire `ingest_docs.py`; golden-query tests. | rag.md, rag_vector_backends.md | L | B | ✅ |
| D | `refactor/structured-outputs` | Replace `parse_json_safe` with native structured outputs / tool-use; drop `langchain` to `langchain-core`. | ADR | M | — | ✅ |
| E | `feat/litellm-client` | Swap the hand-rolled multi-provider client for LiteLLM (keep the `stub` provider); wire real per-model `cost_usd` into the FinOps metrics. | observability.md | M | — | ✅ |
| F | `feat/langgraph-architect` | Real LangGraph tool-loop agent behind `AGENT_BACKEND`; deterministic builtin planner stays the default. | ADR, agents.md | L | C, D | ✅ |
| G | `feat/mcp-server` | Expose the tools/architect over MCP. | ADR, README | M–L | C, E | ✅ |
| H | `feat/pii-presidio` | Presidio detector behind a flag; regex baseline kept. | ADR | M | — | ✅ |
| I | `ci/coverage-gate` | Add a coverage gate and restore the coverage badge; run new tests. | — | S | — | ✅ |

**All PRs above have shipped.** Since then the repo also gained a LangSmith
eval pipeline (golden dataset, code evaluators, calibrated LLM judges,
experiment grid — see docs/langsmith_test_plan.md and docs/eval_results/).

## Status legend

✅ shipped · 🚧 in progress · 🧩 planned. This file is the source of truth for
what those mean per component; individual docs link back here.
