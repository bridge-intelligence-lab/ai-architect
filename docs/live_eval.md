# Live Evaluation for Architect (HTTP + httpx)

This guide shows how to run a live evaluation of the Architect agent using the real OpenAI API and your running service. It streams from the `/architect/stream` endpoint (SSE), measures simple quality metrics, and optionally logs runs to LangSmith for observability.

## Prerequisites
- API running locally (dev or prod-like):
  - `make dev-up` (hot reload, local files mounted), or
  - `make prod-up` (image-only, production-like)
- OpenAI access if you want to test real model outputs:
  - Set in `.env`: `LLM_PROVIDER=openai`, `LLM_MODEL=...`, and `OPENAI_API_KEY=...`
- Python deps for the host running the script:
  - `pip install httpx`

Optional (for observability):
- LangSmith tracing
  - `export LANGCHAIN_TRACING_V2=true`
  - `export LANGCHAIN_API_KEY=...`

## Quickstart

1) Start the API:
```bash
make dev-up
# or
make prod-up
```

2) Run the eval with defaults:
```bash
make eval-live
```
This reads prompts from `eval/architect_prompts.jsonl`, streams SSE from `http://localhost:8000/architect/stream`, and prints a compact report with pass/fail counts.

3) Customize thresholds and prompt file:
```bash
make eval-live FILE=eval/architect_prompts.jsonl LIMIT=5 SUMMARY_MIN=60 STEPS_MIN=3 STEP_CHARS=30
```

## How it works
- `scripts/run_live_eval.py` uses `httpx` (async) to stream SSE lines from `/architect/stream`.
- It extracts `meta`, `summary`, `steps`, `citations`, and `audit` events.
- It scores each run with these defaults:
  - `summary_min_chars=40`
  - `steps_min_count=2`
  - `step_min_chars=20`
- If LangSmith is enabled, each run is logged with metadata (model, provider, grounded) and scores for later comparison.

## Comparing models
- Change `.env` to test different models (e.g., `gpt-4o-mini` vs `gpt-5`).
- Restart the API if needed and re-run `make eval-live`.
- If using LangSmith, view and compare traces by model/provider.

## Notes
- These evals are “live”: they hit real providers and may incur cost and latency.
- For CI, keep using the existing pytest suite which mocks network calls to remain deterministic and fast.
- You can extend the scoring policy in `scripts/run_live_eval.py` if needed.
