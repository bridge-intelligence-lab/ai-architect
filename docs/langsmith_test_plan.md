# LangSmith Test Plan for AI Architect

Goal: go from "traces are flowing, eyeballing outputs" to a repeatable eval setup with a real rubric, experiments, and regression gates.

What we already have:
- 13 categorized prompts in `docs/llm_agent_streaming_prompts.md` (grounded, brainstorm, debugging, memory, CTA)
- 8 more prompts in `eval/architect_prompts.jsonl`
- `scripts/run_live_eval.py` with heuristic scoring (summary_min_chars, steps_min_count, step_min_chars)
- Env-gated tracing in `app/services/architect_agent.py` (LANGCHAIN_TRACING_V2 + LANGCHAIN_API_KEY)

---

## Phase 0: Tracing hygiene (half a day)

Before building evals, make the traces worth evaluating.

1. Open a few traces in LangSmith and check the run tree. Right now `architect_agent.py` creates a single RunTree around the whole request. Ideally you want child runs for: retrieval, LLM call, parsing/fallback. If it is one flat run, evaluators can only judge the final output, not where it went wrong.
2. Add metadata to each run so you can slice later:
   - `model`, `provider`, `grounded_used`
   - RAG flags in effect (multi-query, hyDE)
   - `session_id`
   - prompt category (grounded / brainstorm / debugging / memory / cta) when known
3. Confirm the project name is stable (`LANGCHAIN_TRACING_SESSION_NAME=ai-architect`) so online evaluators and dashboards attach to one project.

## Phase 1: Build the dataset (1 hour)

1. Create a LangSmith dataset `ai-architect-golden` from the 13 + 8 prompts.
2. Each example: `inputs={"question": ...}`, plus `metadata={"category": ...}`.
3. Instead of writing full reference answers (expensive, they rot), record expected *properties* per category:
   - grounded: `expect_citations: true`, `expect_grounded_used: true`
   - brainstorm: citations optional, steps required
   - debugging: must mention specific env vars / fallback behavior (list keywords)
   - all: summary, steps, audit event present
4. Script it (`scripts/build_langsmith_dataset.py`) so the dataset is reproducible, not hand-clicked.

## Phase 2: Rubric = evaluators (the core work, 1-2 days)

Two layers. Cheap deterministic checks catch structure failures; LLM judges catch quality failures.

### Code evaluators (port from run_live_eval.py)
- `has_summary` (>= 40 chars), `steps_count` (>= 2), `step_quality` (>= 20 chars each)
- `citations_present_when_grounded` (uses example metadata)
- `audit_event_emitted`
- `stream_well_formed` (all expected SSE event types arrived: meta, summary, steps, citations, audit)
- latency + time-to-first-token (from trace timings)

### LLM-as-judge evaluators
- **Correctness**: does the answer match what the repo docs actually say? For grounded prompts, pass the retrieved chunks as context and ask the judge to verify claims.
- **Groundedness / hallucination**: are cited files real, are claims supported by the citations?
- **Completeness**: did it answer all parts of the question (files + tests + deployment when asked)?
- **Actionability**: could an engineer follow the steps without guessing?
Score each 1-5 with a short reasoning field. Start with LangSmith's off-the-shelf judge prompts, tune after reading 20-30 judged runs.

### Calibrate the judges
Run the judges over ~20 traces, read every judgment, and fix the judge prompt where you disagree. An uncalibrated judge is worse than no judge.

## Phase 3: Experiments (this is where LangSmith pays off)

Use the `evaluate()` SDK with a target function that streams from `/architect/stream` and assembles the final payload.

Comparisons worth running:
1. Model A vs model B (e.g. gpt-4o-mini vs a bigger model) on the same dataset
2. RAG flags: multi-query on/off, hyDE on/off
3. Prompt changes to the Architect system prompt

LangSmith features to learn here: experiment comparison view, pairwise evaluation (judge picks the better of two outputs), regression highlighting between experiment runs.

## Phase 4: Online evaluation + monitoring

1. Add an **online evaluator rule** on the tracing project: sample 10-25% of live traces, run the groundedness + correctness judges automatically.
2. Set up an **annotation queue**: route low-scoring or flagged runs to a queue, review them by hand, attach feedback. This is how the rubric improves over time.
3. **Dashboards**: latency, token cost, error rate, feedback scores over time.
4. **Alerts** on error rate or score drops.

## Phase 5: Regression gate

- Wrap the golden-dataset eval in a script (`make eval-langsmith`) with pass thresholds per evaluator.
- Run it before merging prompt/RAG/model changes. Later, wire into CI on a schedule (live evals cost money, so nightly rather than per-PR).

---

## Suggested order of attack

| Step | Output | Effort |
|---|---|---|
| 0. Trace hygiene + metadata | sliceable traces | half day |
| 1. Dataset script | `ai-architect-golden` in LangSmith | 1 hr |
| 2a. Code evaluators | structural rubric | half day |
| 2b. LLM judges + calibration | quality rubric | 1 day |
| 3. First experiment (2 models) | comparison you can screenshot | half day |
| 4. Online eval + annotation queue | production feedback loop | half day |
| 5. Regression gate | `make eval-langsmith` | half day |

## LangSmith feature coverage checklist

- [ ] Tracing (run trees, metadata, tags)
- [ ] Datasets and examples
- [ ] Experiments via `evaluate()`
- [ ] Code evaluators
- [ ] LLM-as-judge evaluators
- [ ] Pairwise / comparative evaluation
- [ ] Annotation queues + human feedback
- [ ] Online evaluators (rules on live traffic)
- [ ] Dashboards + alerts
- [ ] Playground (iterate on the Architect prompt against dataset examples)
