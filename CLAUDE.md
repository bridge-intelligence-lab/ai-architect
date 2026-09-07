# CLAUDE.md

Guidance for coding agents working in this repo.

## Commands

`make` (or `make help`) prints every target, self-documented and grouped
(Setup / Test & Lint / Run / Data / Eval / Docker). Highlights:

- `make venv && make install` — setup (Python 3.11+, installs `-e .`)
- `make test` — full suite; offline by design (stub LLM fixture in conftest).
  CI enforces `--cov=app --cov=scripts --cov-fail-under=75`.
- `make serve` — uvicorn on :8000
- `make ingest` — build the Chroma store from DOCS_PATH (needed before
  `RAG_BACKEND=vector` does anything)
- `make dev-up` / `make dev-down` — observability stack, base + dev override
  (Prometheus :9090, Grafana :3001). `make prod-up` runs base only (no override).
- Eval runs (BILLED OpenAI + LangSmith calls, never run casually):
  `make eval PREFIX=<name>` (wraps `scripts/run_langsmith_eval.py`);
  free smoke: `make eval-smoke`. Also `make eval-dataset` (sync golden set,
  `DRYRUN=1` to preview) and `make eval-grid`. Long runs: use nohup (the harness
  streams each example through the live server).

## Architecture in one paragraph

FastAPI app; flagship endpoint is `/architect` (+ `/architect/stream` SSE).
`run_architect_agent` (app/services/architect_agent.py) is the backend-agnostic
entrypoint: it loads short/long memory, dispatches to `AGENT_BACKEND=builtin`
(deterministic planner, the default and the fallback) or `langgraph` (tool loop,
app/services/langgraph_architect.py), applies the feature-CTA heuristic, and
saves memory. Retrieval is behind `RAG_BACKEND` (keyword_scan | vector/Chroma)
in app/services/doc_retriever.py. Every endpoint writes audit rows; costs come
from LiteLLM's pricing map. ADRs live in docs/adr/.

## Corpus rule (important)

`docs/` IS the runtime agent's RAG knowledge base. `docs/worklog/` holds dated
work records (backlogs, approach docs, review reports) and is excluded from the
corpus by default (`RAG_EXCLUDE_DIRS=worklog`); eval prompt docs are excluded
via `RAG_EXCLUDE_FILES`. Consequences:

- A new report/backlog/plan goes in `docs/worklog/YYYY-MM-DD-<topic>.md`,
  never in docs/ root.
- Editing docs/ changes what the agent retrieves and answers. Doc-only PRs can
  move eval metrics; re-run the eval and diff against the latest baseline when
  the corpus changes materially.
- Kept docs carry frontmatter (title, status, module, last_reviewed, source).
  Touch a doc → update last_reviewed; change code a doc's `source` points at →
  review the doc.
- Heading discipline: one H1 right after the frontmatter, real `##`/`###`
  sections (no plain-text label lines acting as headings), no skipped levels.
  Chunkers split on headings, so structure is retrieval quality, not just
  readability.

## Process

- Per-task approach doc first: `docs/worklog/YYYY-MM-DD-approach-<topic>.md`,
  approved before implementation; code review checks conformance to it.
- Eval discipline: two tiers. Invariants (groundedness, correctness,
  no-fabrication judges) almost never change. Shape checks (completeness,
  structure) encode product decisions and evolve with the product. An intended
  behavior change ships its evaluator update in the same PR and re-baselines;
  never silently loosen an evaluator to make a red run green.
- Every PR updates its docs and CHANGELOG.md; merge when CI is green.
- Tests must stay offline: never add a test that hits a paid API (the .env
  leak that made app tests bill OpenAI is documented in CHANGELOG).

## Pointers

- docs/architecture_index.md — system map; docs/agents.md — backends + SSE contract
- docs/rag.md — retrieval config; docs/memory.md — memory tiers
- docs/langsmith_test_plan.md + docs/eval_results/ — eval methodology and verdicts
- docs/worklog/2026-07-04-docs-knowledge-backlog.md — current docs/knowledge backlog
