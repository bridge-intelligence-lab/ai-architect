---
title: Observability notes (Architect memory)
status: current
module: governance
last_reviewed: 2026-07-04
source:
  - app/utils/metrics.py
---

# Observability notes (Architect memory)

- SSE meta event now includes memory read stats when memory flags are enabled:
  - memory_short_reads
  - memory_long_reads
- Audit payload normalizes memory fields to integers/booleans when flags are enabled.
- Set MEMORY_DEBUG=true to print suppressed exceptions from short/long memory operations for troubleshooting in non-production environments.

## Metrics & Dashboards

- For Prometheus/Grafana metrics and how to configure scrapes and dashboards, see observability_metrics.md
- Grafana is published on http://localhost:3001 by docker-compose (container port 3000 remapped)

## LangSmith (tracing + evaluation)

- Server-side tracing is env-gated: set LANGCHAIN_TRACING_V2=true AND a
  LANGCHAIN_API_KEY (no-op without the key); LANGCHAIN_PROJECT names the project.
- The architect run posts a run tree with inputs (question, context blocks) and
  outputs (summary, steps, citations, model, memory read counters).
- The eval pipeline lives on top of the same account: golden dataset sync
  (scripts/build_langsmith_dataset.py), experiment harness
  (scripts/run_langsmith_eval.py), and the experiment grid
  (scripts/run_experiment_grid.py). Results and methodology: docs/eval_results/.

## Audit extras (see docs/audit.md for the full field list)

- agent_backend, agent_tool_calls — which architect backend ran and how many
  tool calls the langgraph loop used
- llm_cost_usd — real per-model cost from LiteLLM's pricing map
- memory_* counters — reads/writes/pruned for both memory tiers
