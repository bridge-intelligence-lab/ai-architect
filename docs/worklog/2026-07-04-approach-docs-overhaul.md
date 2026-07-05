# Approach: docs overhaul (backlog item 4)

Status: APPROVED 2026-07-04
Relates to: 2026-07-04-docs-knowledge-backlog.md item 4; findings report
2026-07-04-docs-review-findings.md (moved into worklog as part of this work).

## Goal

The docs ARE the runtime agent's knowledge (RAG corpus). Remove wrong facts, fix
contradictions, make every kept doc scannable and retrievable, and give coding agents a
CLAUDE.md. Measured against eval baseline `baseline-post-pr27-8b06c0ad`.

## Plan (one PR, logically separated commits)

### Commit 1: corpus restructure
- DELETE: building-with-ai-vs-no-code-dev.md, mlflow-rag-orchestration-idea-from-eric.md,
  architect_deterministic_mode.md (ADR-0007 is the record of what shipped).
- MOVE to docs/worklog/ (date-prefixed, auto-excluded from corpus):
  MODERNIZATION_PLAN.md (all rows shipped; historical), ai-architect-launch.md,
  capabilities_roadmap.md (substantially shipped), live_eval.md (legacy path; short
  pointer to LangSmith pipeline left in docs/eval if referenced), plus the docs-review
  findings report itself.
- KEEP per prior decision: llm_agent_streaming_prompts.md (add note: superseded for
  evals by eval_prompt_set_v2, deliberately RAG-excluded, still linked as starter prompts).

### Commit 2: contradiction + gap fixes (Tier 1, 4, 6 of the findings)
- getting_started: Grafana :3001, correct clone org, kill LC_RAG_BACKEND vocabulary,
  LiteLLM section rewritten around OPENAI_API_KEY + native routing, note ingest step
  needs RAG_BACKEND=vector.
- config.md: correct DB_URL default, real embedding var names, add the headline flags
  (AGENT_BACKEND, RAG_BACKEND, PII_BACKEND, RAG_EXCLUDE_FILES/DIRS, LLM_*).
- rag.md: document both DOCS_PATH defaults + recommend explicit; document
  RAG_EXCLUDE_FILES + RAG_EXCLUDE_DIRS and `make ingest`.
- capabilities_current.md: MCP server + vector backends are shipped, /pii presidio,
  add /think endpoint (also to api.md).
- testing.md: document the CI coverage gate (75%, app+scripts) and the offline
  stub-provider fixture.
- agents.md: tool-budget finalize-now + empty-plan fallback; link the grid verdict;
  memory now backend-agnostic (post PR #27).
- memory.md: /architect integration incl. langgraph path (post PR #27).
- audit/observability: agent_backend, agent_tool_calls, llm_cost_usd fields; LangSmith
  tracing + eval integration section.
- project_guide_rag.md + ingestion_pipelines.md: status headers, real interface/CLI.
- README: fix status paragraph (vector RAG + LangGraph + cost tracking shipped), roadmap
  marks, add Evaluation section linking eval_results/, add eval scripts to layout table.
- README diagram rewrite: /architect as flagship entry with builtin/langgraph fork, RAG
  retrieval path, governance sinks (audit/metrics/tracing); /research demoted to one
  endpoint among others.

### Commit 3: .env.example refresh
- Delete dead: LC_RAG_ENABLED, LLM_ENABLE_RESEARCH, PII_REMEDIATION_INCLUDE_SNIPPETS,
  LANGCHAIN_TRACING_SESSION_NAME (default = delete, per findings; say if you want any
  implemented instead).
- Fix: stub-vs-openai comment contradiction, MLFLOW_EXPERIMENT_NAME default mismatch,
  comment LANGCHAIN_TRACING_V2 needs a key, comment OPENROUTER/AZURE are LiteLLM-consumed.
- Add shipped flags: AGENT_BACKEND, RAG_BACKEND, PII_BACKEND(+threshold/model),
  RAG_EXCLUDE_FILES/DIRS, EVAL_JUDGE_MODEL, research safety (AGENT_LIVE_MODE,
  URL_ALLOWLIST, DENYLIST), router (ROUTER_*), risk (RISK_*), MLflow serving (MLFLOW_*),
  embeddings (LOCAL/OPENAI_EMBEDDING_MODEL, RAG_COLLECTION).
- config.md stops claiming .env.example is complete; instead they're cross-checked.

### Commit 4: frontmatter + formatting normalization
- Frontmatter on every kept docs/*.md: title, status (current|historical), module
  (router|rag|agents|memory|governance|ops|eval), last_reviewed, source (code paths).
- Verify loader behavior with frontmatter (chunking check); keep it to ~6 lines.
- Normalize structure: purpose line under H1, consistent heading hierarchy, split
  wall-of-text sections. Full normalization only where a doc is already being touched;
  untouched accurate docs get frontmatter only (keeps the diff reviewable).
- docs/README.md index refreshed: add eval docs, remove deleted/moved entries.

### Commit 5: CLAUDE.md v1
- Commands (make targets, test, eval runs + billed-API warning), AGENT_BACKEND split,
  corpus rule (docs/ ingested, docs/worklog/ excluded, approach-doc process), eval
  discipline (invariant vs shape evaluators, update evals in same PR as behavior
  changes), pointers to ADRs + key docs.

## Verification
- Full test suite (RAG exclusion tests must still pass; some tests may reference
  deleted docs — will fix in-PR).
- `python scripts/ingest_docs.py` rebuild + eval re-run, diff vs
  `baseline-post-pr27-8b06c0ad` in LangSmith. Expect groundedness/citations to hold or
  improve; report the diff before merge.

## Out of scope
- Module docs per subsystem (backlog item 5).
- Makefile revamp (item 7) beyond documenting existing targets.
- Any behavior change; this PR is docs + .env.example + CLAUDE.md only.
