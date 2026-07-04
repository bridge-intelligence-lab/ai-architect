# Changelog

## [Unreleased]

### Added

* LS-8 experiment grid (`scripts/run_experiment_grid.py`): cycles .env per cell (AGENT_BACKEND x LLM_MAX_TOKENS), trips the uvicorn reloader, health-gates, runs the golden dataset, verifies each experiment's audit backend, restores .env. Verdict in `docs/eval_results/2026-07-04-grid-backend-tokens.md`: langgraph beats builtin on groundedness/correctness/completeness AND latency; 1024 tokens never truncates. Evaluators now also emit `cost_usd` and `completion_tokens` feedback so experiments aggregate spend.

* Judge calibration round 1 (`docs/eval_calibration_2026-07-04.md`): all 26 baseline judgments audited against the codebase; judge prompts gained hard rules (empty answer scores 1 everywhere, truncated snippet fragments are not evidence), a correctness cap when the question goes unanswered, grounding-aware completeness, and question-type-aware actionability. Re-judging the same answers moved completeness 3.85→3.38 and actionability 2.73→3.62. Also surfaced: the RAG corpus retrieves `docs/llm_agent_streaming_prompts.md` (the old test-prompt list) as context for eval questions, and the CI coverage gate is undocumented under docs/.

* LangSmith LLM-judge evaluators and experiment harness (`scripts/langsmith_judges.py`, `scripts/run_langsmith_eval.py`): four 1-5 judges (correctness, groundedness, completeness, actionability) via litellm, judge prompts versioned in code; harness streams `/architect/stream` per dataset example and runs code evaluators + judges through `langsmith.evaluate()` with experiment metadata (agent backend, max tokens). Offline tests in `tests/test_langsmith_harness.py`.

* LangSmith code evaluators (`scripts/langsmith_evaluators.py`): deterministic structural checks for experiment runs, ported from `run_live_eval.py` and extended with dataset-expectation checks (grounded/citations match, keywords, stream well-formedness, token-cap truncation, latency/TTFT). Category-aware: structure checks skip the negative/adversarial prompt set. Offline tests in `tests/test_langsmith_evaluators.py`.

* LangSmith golden dataset tooling (`scripts/build_langsmith_dataset.py`): idempotent sync of `eval/architect_prompts_v2.jsonl` (26 prompts: grounded-core, new-features, negative/adversarial) into the `ai-architect-golden` dataset, keyed by example id with create/update/delete and `--dry-run`. Prompt set reviewed in `docs/eval_prompt_set_v2.md`; plan and backlog in `docs/langsmith_test_plan.md` / `docs/langsmith_eval_backlog.md`.

* CI coverage gate: tests run with `pytest-cov` and fail under 75% line coverage (current baseline: 79%); coverage config in `pyproject.toml`, gate badge in the README.

* Presidio PII backend behind `PII_BACKEND=presidio` (`app/services/pii_presidio.py`): NER + pattern recognizers with per-entity confidence scores (`PII_PRESIDIO_THRESHOLD`, `PII_SPACY_MODEL`); optional install via `pip install .[presidio]`; regex baseline stays the default and the fallback, and results report `pii_backend` = backend actually used (`docs/adr/0009-presidio-pii-backend.md`).

* MCP server (`app/mcp_server.py`, console script `ai-architect-mcp`): exposes `retrieve_docs`, `detect_pii`, and `architect_plan` over the Model Context Protocol via the official SDK's FastMCP on stdio; backend flags (`RAG_BACKEND`, `AGENT_BACKEND`, `LLM_PROVIDER`) apply unchanged and audit metadata rides along in tool results (`docs/adr/0008-mcp-server.md`).

* Real LangGraph tool-loop architect behind `AGENT_BACKEND=langgraph` (`app/services/langgraph_architect.py`): the LLM decides per turn between calling `retrieve_docs` (via `doc_retriever`, vector backend applies) and finalizing; capped at 3 tool calls; tokens/cost accumulate across turns; audit reports `agent_backend` and `agent_tool_calls`. The deterministic builtin planner stays the default and the fallback on any failure (`docs/adr/0007-langgraph-architect.md`).

* LiteLLM-backed `LLMClient`: all real providers route through `litellm.completion` (the hand-rolled openai/openrouter/azure branches are gone); the deterministic offline `stub` provider stays the default and the fallback on any provider error. `cost_usd` is now real, from LiteLLM's per-model pricing map, and `app/utils/cost.py` prices its estimates from the same map (static table only as fallback). Tests: `tests/test_llm_cost.py`.

* Real vector retrieval behind `RAG_BACKEND=vector`: Chroma-backed `app/services/vector_retriever.py` with cosine ranking over chunked documents; `scripts/ingest_docs.py` now actually ingests (chunk + embed + upsert, idempotent ids); keyword scan remains the default and the fallback when the vectorstore is missing or empty; audit `rag_backend` reports the backend actually used.
* Deterministic `hash` embeddings provider (hashed bag-of-words) for offline golden-query tests; `EMBEDDINGS_PROVIDER=local|hash|stub`.
* `tests/test_vector_rag.py`: golden-query ranking, determinism, vector→keyword fallback, endpoint audit reporting, and empty-corpus (no fabricated citations) contracts.

### Fixed

* RAG corpus exclusions (`RAG_EXCLUDE_FILES`): eval/test-prompt docs (the v1 streaming prompt list and the LangSmith eval docs) are excluded from grounding by default across the keyword scan, its fallbacks, vector ingestion, and vector query (query-time filter catches stale chunks). Found during judge calibration: eval questions retrieved the question list itself as context. Tests in `tests/test_rag_exclusions.py`.

* LangGraph architect no longer returns empty plans when it hits the tool-call cap: the agent is told the retrieval budget is exhausted and must finalize; if the plan still has no summary the builtin planner takes over (found by LangSmith eval baseline: 8/18 grounded prompts affected).
* Tests no longer inherit the developer's `.env` (loaded with `override=True` by `app/main.py` at import): an autouse fixture pins the stub provider and clears provider/tracing keys, ending silent live OpenAI calls from the suite.

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
