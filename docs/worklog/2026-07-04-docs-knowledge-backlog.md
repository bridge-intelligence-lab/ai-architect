# Docs & Knowledge Backlog - 2026-07-04

Brainstormed 2026-07-04. Goal: improve the agent's knowledge of its own
system, clean the RAG corpus, and make responses intent-flexible, without losing the eval
work from PRs #19-#26.

Convention adopted in that session: `docs/` describes the system as it is (RAG-ingested);
`docs/worklog/` records work as it happened (dated prefix, excluded from ingestion). This
file is the first entry.

## Sequence

### 1. Debug session memory + UI SSE [DONE - PR #27]
- Symptoms: agent not remembering session conversation; UI SSE apparently not streaming.
- Likely one root cause (conversation-state/streaming plumbing). Suspect eval-day changes
  (#19-#26), especially the .env/test-leak fix and #26.
- Plan: reproduce both in UI, verify session store writes in backend logs, curl the SSE
  endpoint directly to isolate server vs UI client. Fallback: bisect against pre-#19.

### 2. Fix GitHub-issue-offer regression [DONE - PR #27, same root cause as 1]
- Build/collaborate intent used to offer creating a GitHub issue to start the work; gone now.
- Golden dataset (26 prompts) does not cover this behavior, so it broke silently.
- Plan: `git log -p` over prompt files to bisect, fix, then add 2-3 golden prompts + an
  evaluator check so it is regression-gated.

### 3. Baseline eval run [DONE 2026-07-04]
- Experiment: `baseline-post-pr27-8b06c0ad` (26/26 examples, post-PR-#27 config:
  langgraph + memory parity, gpt-4.1, 1024 tokens, vector RAG).
- Key numbers to diff after the docs overhaul:
  judge_groundedness 3.346, judge_correctness 3.308, judge_completeness 2.885,
  judge_actionability 2.923, citations_expectation 0.833,
  grounded_matches_expectation 0.846, keywords_present 0.833,
  latency mean 10.6s (max 33.2s), cost $0.006/prompt, not_truncated 1.0.
- ttft equals latency by design for now: the SSE status ack is excluded from ttft and
  content events arrive only after the agent completes (no token streaming yet).

### 4. Docs overhaul PR (one sweep, one corpus change)
- Delete: building-with-ai-vs-no-code-dev.md, mlflow-rag-orchestration-idea-from-eric.md,
  architect_deterministic_mode.md (ADR-0007 is the record), dead env vars in .env.example
  (LC_RAG_ENABLED, LLM_ENABLE_RESEARCH, PII_REMEDIATION_INCLUDE_SNIPPETS).
- Move to worklog/ with date prefix instead of delete: MODERNIZATION_PLAN.md,
  ai-architect-launch.md, capabilities_roadmap.md, eval/backlog/review reports,
  projects/ai-architect-docs-review-2026-07-04.md findings.
- RAG exclude: verify RAG_EXCLUDE_FILES supports directories/globs; if not, small loader
  change so docs/worklog/ is excluded by default (excluded-by-default is the point).
- Frontmatter on kept docs: title, status (current/superseded/historical), module,
  last_reviewed, source (paths to code the doc describes). No Obsidian wikilinks; plain
  relative md links. Check loader does not chunk YAML as text.
- Formatting normalization: one lightweight template per doc type (concept/how-to/reference),
  purpose line up top, real heading hierarchy (chunkers split on headings, so this is also
  a retrieval improvement).
- Diagram fix: README "System Architecture" shows /research as the only agent; rewrite with
  /architect as entry point, builtin/langgraph fork, RAG path, governance sinks; demote
  /research to one endpoint.
- CLAUDE.md v1: build/test/eval commands (note evals hit billed APIs), AGENT_BACKEND split,
  corpus rule (docs/ ingested, worklog/ not), pointers to ADRs, eval discipline
  (invariant vs shape evaluators; evaluator changes ship in the same PR as intended
  behavior changes).
- After merge: re-run evals, diff vs step-3 baseline. Groundedness should hold or improve.

### 5. Module docs + docstrings
- One page per subsystem: router, RAG pipeline, builtin agent, langgraph agent, governance.
  What it owns, contracts, why it exists. These are the "agent deep understanding" layer;
  they go into the corpus.
- Docstrings written opportunistically while producing them (public surfaces first:
  routers, services, both agent backends). Docstrings serve maintainers/coding agents;
  module docs serve the runtime agent.
- CLAUDE.md matures alongside (mostly pointers into module docs).

### 6. Intent-flexible responses
- Cheap prototype first: keep schema, make `steps` optional, router intent picks response
  template. Deeper per-mode contracts only if evals say the cheap version helps.
- Mode-aware edits to shape-tier evaluators (completeness, structure) ship in the same PR;
  invariant tier (groundedness, correctness, LS-7 calibration) untouched.
- Re-baseline after.

### 7. Makefile revamp
- Better `make help` (self-documenting targets, grouped: dev, test, eval, docker, docs).
- Full revamp, not just help text: audit targets for dead/duplicated ones while at it.
- May pull docker-compose improvements along with it; scope that as part of the
  item-8 discussion so the ops surface (make + compose + dashboards) is designed once.
- Eval-neutral chore otherwise; natural companion to the CLAUDE.md commands section
  in step 4.

### 8. Ops surface: LiteLLM + Grafana dashboards + docker-compose [DISCUSSION FIRST]
- Current dashboards are poor and not fully connected to each other.
- Needs a requirements conversation before any work: what questions should the dashboards
  answer (cost per request/model? latency percentiles? RAG hit quality? eval-run cost?),
  and how LiteLLM metrics and app traces join up.
- docker-compose review folded in here: service layout, ports, healthchecks, whatever the
  Makefile revamp surfaces. Decide make/compose/dashboards together, implement after.
- Note: Grafana locally remapped to 3001 (cognee-frontend owns 3000), change uncommitted;
  docker-compose.yml also has uncommitted local changes.

### 9. Move audit.db to data folder
- Small chore: relocate audit.db out of repo root into data/, update path config,
  gitignore if not already.

## Process (adopted this session)
- approach.md pattern adopted (community practice): per-task
  approach doc written BEFORE implementation, approved as the gate; code review checks
  conformance to it. Adopt as `docs/worklog/YYYY-MM-DD-approach-<topic>.md` per work item.

## Eval policy (agreed)
- Two tiers: invariants (groundedness, correctness, no fabrication) almost never change;
  shape checks (completeness, structure) evolve with the product.
- Regression = unintended metric drop, eval wins. Spec change = intended, update evaluator
  in same PR, re-run new evaluator against old baseline, version the dataset.
- Never silently loosen an evaluator to turn a red run green.

## Decisions (answered 2026-07-04)
- Judgment-call deletes: KEEP llm_agent_streaming_prompts.md; logo jpg renamed to
  docs/images/logo.jpg locally.
- Uncommitted local changes (.coverage, architect_form.html, docker-compose.yml,
  ai-architect-launch.md): include in first PR.
