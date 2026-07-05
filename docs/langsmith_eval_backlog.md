---
title: Backlog: LangSmith Eval Setup for AI Architect
status: current
module: eval
last_reviewed: 2026-07-04
---

# Backlog: LangSmith Eval Setup for AI Architect

Companion to `docs/langsmith_test_plan.md`. Work items in dependency order. Nothing starts until this doc is reviewed.

Status legend: `todo` / `in-progress` / `review` / `done`

## Branching / PR convention

- **One feature branch per epic**, cut from `main`: `feat/eval-epic-<n>-<slug>` (e.g. `feat/eval-epic-1-trace-hygiene`). One PR per epic; epic 3 lands with judges/calibration as clearly separated commits on the same branch.
- One commit per LS item as the default. Exceptions: LS-1 (findings go in the PR description, no commit) and LS-7 calibration (multiple tuning commits, messages like "calibrate groundedness judge: penalize invented env vars").
- Docs (this backlog, test plan, prompt set) ship as PR 0 on `docs/langsmith-eval-plan` before epic work starts; approving PR 0 closes LS-4a.
- Epic 5 is a docs-only PR: a runbook capturing the LangSmith UI config (rules, sample rates, alert thresholds) since that config lives outside the repo.
- Per repo convention (`MODERNIZATION_PLAN.md`): every PR carries its docs and a `CHANGELOG.md` entry, merged when CI (75% coverage gate) is green.

---

## Epic 1: Trace hygiene

### LS-1: Audit current trace structure

- **Status:** todo
- **Effort:** 1-2 hrs
- **What:** Open 5-10 recent traces in LangSmith. Document what the run tree looks like today: is it one flat run per request, or are retrieval / LLM call / parse-fallback visible as child runs? Note what metadata is already attached.
- **Acceptance:** Short findings note (can be a comment on this doc) listing current tree shape and metadata gaps.
- **Depends on:** nothing

### LS-2: Add child runs for pipeline stages

- **Status:** todo
- **Effort:** half day
- **What:** In `app/services/architect_agent.py`, split the single RunTree into child runs: retrieval, LLM call, parsing/fallback. Keep it env-gated as today.
- **Acceptance:** A new trace in LangSmith shows the nested tree. No behavior change when tracing is off (existing pytest suite passes).
- **Depends on:** LS-1

### LS-3: Attach run metadata for slicing

- **Status:** todo
- **Effort:** 1-2 hrs
- **What:** Add to each root run: model, provider, grounded_used, RAG flags (multi-query, hyDE), session_id. Confirm project name is stable via `LANGCHAIN_TRACING_SESSION_NAME`.
- **Acceptance:** Filter traces in LangSmith UI by model and by grounded_used and get correct subsets.
- **Depends on:** LS-1 (can run parallel to LS-2)

## Epic 2: Golden dataset

### LS-4a: Curate + refresh prompt set (v2)

- **Status:** done (approved via PR #19)
- **Effort:** 2-3 hrs
- **What:** Review of the year-old prompts (2026-07-04) found them factually still valid but coverage-poor: written as a streaming-UI smoke test, zero coverage of post-2025 features (MCP server, Presidio PII, risk scorer, think planner, LangGraph architect), no negative/adversarial cases, and overlap between the md and jsonl sets. v2 set: 10 kept grounded-core + 8 new-features + 8 negative/adversarial = 26 prompts with per-example metadata (category, expect_grounded, expect_citations, keywords).
- **Acceptance:** Rodrigo approves `docs/eval_prompt_set_v2.md` including its 3 open questions (brainstorm category, Portuguese prompt, B-set gaps).
- **Depends on:** nothing
- **Note:** The LangGraph architect already shipped behind `AGENT_BACKEND=langgraph` (deterministic planner remains default). Re-run A6-A8 and B7 against both backends once experiments exist (LS-8).

### LS-4b: Dataset build script

- **Status:** review
- **Effort:** 2-3 hrs
- **What:** `scripts/build_langsmith_dataset.py`. Consumes the approved v2 set (as jsonl checked into `eval/`, generated from the doc). Creates/updates dataset `ai-architect-golden`. Each example carries `metadata.category` and expected-property flags read by evaluators.
- **Acceptance:** Running the script twice is idempotent (updates, no duplicates). Dataset visible in LangSmith with 26 examples, categories filterable.
- **Depends on:** LS-4a

## Epic 3: Rubric (evaluators)

### LS-5: Code evaluators

- **Status:** done (commit on epic-3 branch)
- **Effort:** half day
- **What:** Port heuristics from `scripts/run_live_eval.py` into LangSmith evaluator functions: has_summary (>= 40 chars), steps_count (>= 2), step_quality (>= 20 chars each), citations_present_when_grounded (reads example metadata), audit_event_emitted, stream_well_formed (meta, summary, steps, citations, audit all arrived), truncated (output cut by max_tokens: finish_reason or malformed-JSON tail; needed so LS-8 axis 2 shows truncation as a named cause, not mystery low completeness), latency + TTFT from trace timings.
- **Acceptance:** Each evaluator returns a named score; a test run over 3 examples shows scores in the experiment view.
- **Depends on:** LS-4b

### LS-6: LLM-as-judge evaluators

- **Status:** done (verified via baseline-fixed-v3-3def7580)
- **Effort:** 1 day
- **What:** Four judges scoring 1-5 with reasoning: correctness (vs repo docs / retrieved chunks), groundedness (claims supported by citations, cited files exist), completeness (all parts of the question answered), actionability (steps followable without guessing). Start from LangSmith off-the-shelf prompts.
- **Acceptance:** Judges run via `evaluate()` on the full dataset without errors; scores + reasoning visible per example.
- **Depends on:** LS-4b, LS-5 (target function reuse)

### LS-7: Judge calibration pass

- **Status:** done (see docs/eval_calibration_2026-07-04.md; delegated to Hue, verified against code)
- **Effort:** half day
- **What:** Read every judgment from one full run (~21 x 4). Where you disagree, adjust the judge prompt and re-run. Record disagreement rate before/after.
- **Acceptance:** Documented calibration note; disagreement on a spot-check < ~10%.
- **Depends on:** LS-6

## Epic 4: Experiments

### LS-8: evaluate() harness + first experiment

- **Status:** done (see docs/eval_results/2026-07-04-grid-backend-tokens.md; winners = langgraph + 1024, already in .env)
- **Effort:** half day
- **What:** `scripts/run_langsmith_eval.py` with a target function that streams `/architect/stream` (SSE) and assembles the final payload. First experiment is a 2x2 grid over two live config questions instead of deciding them upfront (from .env review 2026-07-04): `AGENT_BACKEND` builtin vs langgraph, and `LLM_MAX_TOKENS` 1024 vs 2048. Four experiments x 26 prompts. Verdict metrics: backend axis = correctness/groundedness + latency + cost; token axis = completeness + the LS-5 `truncated` evaluator. Experiments tagged with their config.
- **Acceptance:** Four experiments comparable side by side in LangSmith; a short writeup answering both config questions with scores, after which .env gets set to the winners.
- **Depends on:** LS-5, LS-6

### LS-9: RAG flag experiments

- **Status:** todo
- **Effort:** half day
- **What:** DESIGN CORRECTED 2026-07-04: multi-query/hyDE flags are no-ops under RAG_BACKEND=vector (they only affect the keyword scan). Round two axes instead: RAG_BACKEND vector vs keyword_scan, and the model shootout gpt-4.1 vs gpt-4.1-mini (judges upgraded via EVAL_JUDGE_MODEL for that run).
- **Acceptance:** 3-4 experiments tagged by flag combo; findings noted in `docs/eval_results/` (chosen).
- **Depends on:** LS-8

## Epic 5: Production loop

### LS-10: Online evaluator rule

- **Status:** todo
- **Effort:** 2-3 hrs
- **What:** Rule on the tracing project sampling 10-25% of live traces, running groundedness + correctness judges automatically.
- **Acceptance:** New live traffic shows judge scores appearing without manual runs.
- **Depends on:** LS-7

### LS-11: Annotation queue

- **Status:** todo
- **Effort:** 1-2 hrs
- **What:** Queue receiving low-scoring / flagged runs for human review. Define the feedback schema (thumbs + free text is enough to start).
- **Acceptance:** A flagged run lands in the queue, gets reviewed, feedback attached to the trace.
- **Depends on:** LS-10

### LS-12: Dashboard + alerts

- **Status:** todo
- **Effort:** 2-3 hrs
- **What:** Dashboard for latency, token cost, error rate, judge scores over time. Alert on error-rate spike or score drop.
- **Acceptance:** Dashboard exists; one test alert fired and received.
- **Depends on:** LS-10

## Epic 6: Regression gate

### LS-13: make eval-langsmith with thresholds

- **Status:** todo
- **Effort:** half day
- **What:** Makefile target wrapping LS-8 harness with pass/fail thresholds per evaluator. Nightly-friendly (live evals cost money, not per-PR).
- **Acceptance:** Exits nonzero when a threshold is breached; thresholds documented in the script.
- **Depends on:** LS-8

---

## Sequencing summary

Parallel start: LS-1 and LS-4a.
Critical path: LS-4a -> LS-4b -> LS-5 -> LS-6 -> LS-7 -> LS-10.
Total: roughly 4-5 days of focused work, deliverable in slices. Each epic leaves something usable even if we stop there.

## Open questions for review

1. Model pair for the first experiment (LS-8)?
2. Budget ceiling for judge calls? Judges on 21 examples x 4 rubrics per experiment is cheap, but online eval (LS-10) sampling live traffic is ongoing spend.
3. Do we care about pairwise (A/B judge picks winner) in the first pass, or is scalar scoring enough? Currently left out of the backlog.
4. Where do experiment writeups live: `docs/eval_results/` (chosen)
