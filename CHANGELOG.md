# Changelog

## [Unreleased]

### Added

* Real LangGraph tool-loop architect behind `AGENT_BACKEND=langgraph` (`app/services/langgraph_architect.py`): the LLM decides per turn between calling `retrieve_docs` (via `doc_retriever`, vector backend applies) and finalizing; capped at 3 tool calls; tokens/cost accumulate across turns; audit reports `agent_backend` and `agent_tool_calls`. The deterministic builtin planner stays the default and the fallback on any failure (`docs/adr/0007-langgraph-architect.md`).

* LiteLLM-backed `LLMClient`: all real providers route through `litellm.completion` (the hand-rolled openai/openrouter/azure branches are gone); the deterministic offline `stub` provider stays the default and the fallback on any provider error. `cost_usd` is now real, from LiteLLM's per-model pricing map, and `app/utils/cost.py` prices its estimates from the same map (static table only as fallback). Tests: `tests/test_llm_cost.py`.

* Real vector retrieval behind `RAG_BACKEND=vector`: Chroma-backed `app/services/vector_retriever.py` with cosine ranking over chunked documents; `scripts/ingest_docs.py` now actually ingests (chunk + embed + upsert, idempotent ids); keyword scan remains the default and the fallback when the vectorstore is missing or empty; audit `rag_backend` reports the backend actually used.
* Deterministic `hash` embeddings provider (hashed bag-of-words) for offline golden-query tests; `EMBEDDINGS_PROVIDER=local|hash|stub`.
* `tests/test_vector_rag.py`: golden-query ranking, determinism, vector→keyword fallback, endpoint audit reporting, and empty-corpus (no fabricated citations) contracts.

### Changed

* Rename `app/services/langchain_rag.py` → `app/services/doc_retriever.py`; the module is a deterministic keyword-scan retriever and never used LangChain (`docs/adr/0005-doc-retriever-naming.md`).
* Retire placeholder response paths: grounded `/query` answers are now extractive (built from matched snippets) instead of a hardcoded stub sentence; the fabricated `synthetic` citation fallback is removed; `audit.rag_backend` reports `keyword_scan`.
* Rewrite `docs/rag.md` to describe the retrieval path that actually exists; the vector backend remains planned work (plan row C).

### Removed

* Delete dead `app/services/prompt_runner.py` (`parse_json_safe` and the `LC_USE_OUTPUT_PARSER` flag); the live structured-output path in `architect_agent` already validates against the `ArchitectPlan` pydantic model (`docs/adr/0006-structured-outputs.md`).
* Drop the stale `langchain==0.1.11` dependency; `langchain-core` remains the only LangChain dist, used for typed output parsing.

### Docs

* Add `docs/MODERNIZATION_PLAN.md` and `docs/adr/0004-build-vs-buy.md`, sequencing the 2026 modernization (real vector retrieval, native structured outputs, LiteLLM cost tracking, LangGraph agent, optional MCP) as small per-PR changes with a build-vs-buy rationale per component.
* Scope the repo to its single purpose — a reference implementation for running LLM/agent services with production controls — and remove the standalone Mandala design documents from HEAD (preserved in git history).
* Refresh the README: scope statement, per-component shipped-vs-planned roadmap, and badge/URL updates for the `bridge-intelligence-lab` org.

## [0.9.0] - 2025-10-07

### Added

* `/architect` endpoint as unified meta-agent orchestrator for RAG, Agents, and MLflow.
* Architect UI with streaming and SSE support.
* Governance layer: audit logs, cost tracking, FinOps metrics.
* Observability stack with Prometheus and Grafana integration.
* Full documentation suite (`/docs`): API, RAG, Router, Risk, PII, Memory, Observability, and MLOps plans.
* RBAC implementation, PII detection, and risk scoring sub-agents.
* Prompt registry and deterministic retrieval pipeline.

### Changed

* Refactored `README.md` to center around the `/architect` endpoint.
* Reorganized project structure into modular components (`app/routers`, `app/services`, etc.).
* Unified routing logic and deterministic RAG paths.
* Updated CI workflows and Makefile for testing and OpenAPI export.
* Enhanced audit DB schema for cost and latency tracking.

### Fixed

* Streaming response stability issues in Architect UI.
* MLflow drift detection edge cases.
* Minor type and logging inconsistencies across routers.

---

## [0.1.0] - Initial Commit

### Added

* Initial FastAPI skeleton and basic `/query` endpoint.
* Early agentic and retrieval experimentation.
* Bootstrap for documentation, Makefile, and project scaffolding.

---

## 🧭 Maintaining the Changelog

To keep this file useful and accurate:

1. **For each new version tag**, add a section at the top following the format:

   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD
   ### Added
   - ...
   ### Changed
   - ...
   ### Fixed
   - ...
   ```

2. **Follow semantic versioning**:

   * **MAJOR**: Breaking changes or major refactor (`1.0.0` → `2.0.0`).
   * **MINOR**: New features, backward compatible (`0.9.0` → `0.10.0`).
   * **PATCH**: Fixes and small tweaks (`0.9.0` → `0.9.1`).

3. **Tag releases** in git:

   ```bash
   git tag -a v0.10.0 -m "Your summary here"
   git push origin v0.10.0
   ```

4. **Link to GitHub releases**: copy key highlights from each entry to the release description for visibility.

Keeping this file updated ensures transparency for contributors and users reviewing the project's
