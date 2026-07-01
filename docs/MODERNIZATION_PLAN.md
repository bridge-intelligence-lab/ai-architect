# Modernization Plan

This repo was first written in late 2025 while learning the LLM/agent stack. A
lot of capability was hand-rolled rather than pulled from a framework. That was a
deliberate learning choice and, in several places, remains the right call. This
plan records where hand-rolled stays (documented as a build-vs-buy decision) and
where a library genuinely earns its place, and sequences the work into small,
reviewable PRs.

See [ADR-0004: Build-vs-buy policy](adr/0004-build-vs-buy.md) for the per-component
rationale, and [ADR-0001: Ports-and-Adapters](adr/0001-ports-and-adapters.md) for the
seam these changes slot into (real adapters filling existing ports).

## Principles

- **Match claims to code first.** No feature is described as shipped until the
  code does it. Honesty PR (A) lands before the up-levels.
- **Adopt a library only when the hand-rolled version is worse on a real axis**
  (a false claim, a reliability liability, or an unmet capability), not for
  fashion. Modernizing here mostly *reduces* framework coupling.
- **One short-lived branch per PR off `main`,** merged when CI is green. Each PR
  is independently valuable and revertible.
- **Every PR carries its docs:** an ADR for any decision, updates to the relevant
  `docs/*.md`, and a `CHANGELOG.md` entry.

## Locked decisions

- **Agent (PR F): build a real LangGraph agent.** The architect is currently a
  linear chain. Rather than rename it, we implement a genuine tool-loop agent on
  LangGraph, which also retires the (previously false) "LangGraph" roadmap claim
  by actually delivering it.
- **LangChain (PR D): drop it, keep only `langchain-core`.** The pinned
  `langchain==0.1.11` is load-bearing in exactly the spots being modernized
  (a dead `langchain.schema` import, and a "RAG" module that imports no
  langchain). Native structured outputs remove the need for the heavyweight
  package; `langchain-core` stays only for typed output parsers.

## PR sequence

| # | Branch | Scope | Docs | Size | Depends on |
|---|--------|-------|------|------|------------|
| A | `docs/honesty-and-adrs` | Reconcile README/roadmap to reality; this plan; build-vs-buy ADR. No code behavior change. | ADR-0004, README | S | — |
| B | `refactor/rag-honest-naming` | Rename `langchain_rag.py` → `doc_retriever.py`; remove the hardcoded stub-answer string and the fake HyDE/multi-query labels. | rag.md | S | A |
| C | `feat/vector-rag` | Real embeddings (sentence-transformers) + Chroma retrieval behind `RAG_BACKEND`; keep deterministic baseline as fallback; wire `ingest_docs.py`; golden-query tests. | rag.md, rag_vector_backends.md | L | B |
| D | `refactor/structured-outputs` | Replace `parse_json_safe` with native structured outputs / tool-use; delete dead `langchain.schema` import; drop `langchain` to `langchain-core`. | ADR | M | — |
| E | `feat/litellm-client` | Swap the hand-rolled multi-provider client for LiteLLM (keep the `stub` provider); populate real `cost_usd` so FinOps metrics stop being 0.0. | observability.md | M | — |
| F | `feat/langgraph-architect` | Real LangGraph tool-loop agent behind `AGENT_BACKEND`; deterministic builtin planner stays the default. | ADR, agents.md | L | C, D |
| G | `feat/mcp-server` | Expose the tools/architect over MCP. High "2026-current" signal. | ADR, README | M–L | C, E |
| H | `feat/pii-presidio` | Presidio detector behind a flag; regex baseline kept. | ADR | M | — |
| I | `ci/coverage-gate` | Add the coverage gate the codecov badge implies (or drop the badge); run new tests. | — | S | — |

**Recommended order:** A → B → C → D → E → F, then optional G / H / I.

## Status legend

✅ shipped and true · 🚧 in progress · 🧩 planned. This file is the source of
truth for what those mean per component; individual docs link back here.
