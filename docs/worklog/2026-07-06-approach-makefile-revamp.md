# Approach: Makefile revamp (backlog item 7)

Status: APPROVED (greenlit to start 2026-07-06; item 6 deferred as an epic)
Relates to: docs/worklog/2026-07-04-docs-knowledge-backlog.md item 7.

## Goal

The Makefile grew target-by-target; `make help` is a single hardcoded echo
line that already drifts from the real targets (it omits `test-docker` and
`eval-live`). Make it self-documenting and grouped, and audit for
dead/duplicated targets while in there. Eval-neutral chore.

## Audit findings (pre-work)

- **`help` is stale and manual.** Lists 15 targets by hand; misses
  `test-docker` and `eval-live`. Any new target silently falls off.
- **`dev-up` vs `prod-up` are NOT duplicates.** `docker-compose.override.yml`
  exists, so `docker compose up` (dev-up) merges base+override while
  `docker compose -f docker-compose.yml up` (prod-up) loads base only. Real
  distinction — keep both, but document it so it isn't mistaken for dead code.
- **No dead targets.** All referenced scripts exist
  (ingest_docs / sweep_retention / export_openapi / run_live_eval).
- **Under-exposed scripts.** `run_langsmith_eval.py`,
  `build_langsmith_dataset.py`, `run_experiment_grid.py` are the current eval
  surface but have no targets; only the legacy `run_live_eval.py` does. CLAUDE.md
  already tells people to call `python scripts/run_langsmith_eval.py ...` by hand.
- **No docs build system** (no mkdocs/sphinx) — docs are plain markdown for the
  RAG corpus, so a "docs" group means the data/RAG targets (ingest,
  export-openapi), not a site build.

## Proposed change

**Self-documenting help.** Standard `##`-annotation + `##@` group-header awk
pattern. `.DEFAULT_GOAL := help`. Each target documents itself inline; `make`
or `make help` prints grouped, aligned output. New targets self-register.

**Groups:** Setup / Test & Lint / Run / Data / Eval / Docker.

**New eval targets** wrapping the current scripts (all BILLED except smoke):
- `eval` — `run_langsmith_eval.py` (vars: `PREFIX`, `LIMIT`, `NOJUDGES=1`)
- `eval-smoke` — 3 examples, `--no-judges` (free/fast)
- `eval-dataset` — `build_langsmith_dataset.py` (`DRYRUN=1` to preview)
- `eval-grid` — `run_experiment_grid.py` (`CELLS="..."`)
- `eval-live` — kept as-is (legacy deterministic harness, its own vars)

**Out of scope (deferred to item 8):** no docker-compose edits, no port/service/
dashboard changes. This PR only touches the Makefile and the CLAUDE.md commands
list that mirrors it. Compose ownership stays with the item-8 ops discussion.

## Verification

- `make help` renders grouped and includes every target (grep every
  `^[a-z].*:` target appears in help output).
- `make -n <target>` dry-runs unchanged for existing targets (venv, install,
  test, serve, lint, ingest, sweep, freeze, export-openapi, dev-*, prod-*,
  logs, test-docker, eval-live) — command bodies must be byte-identical.
- CLAUDE.md Commands section updated to match (no invented targets).
- Eval-neutral: no app/eval code touched, so no eval re-run required.
