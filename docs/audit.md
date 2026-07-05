---
title: Auditing & Retention
status: current
module: governance
last_reviewed: 2026-07-04
source:
  - app/utils/audit.py
  - app/db/
---

# Auditing & Retention

## Audit writes
- Function: app.utils.audit.write_audit
- Non-blocking behavior: DB errors are caught, transaction rolled back, and error logged. API flow continues.
- Fields include: request_id, endpoint, user_id, created_at, tokens_prompt/completion, cost_usd, latency_ms, compliance_flag, prompt_hash, response_hash.
- Per-feature extras ride along in the audit payload: rag_backend (+ query-expansion flags on the keyword path), agent_backend and agent_tool_calls (architect), llm_provider/llm_model/llm_cost_usd (real cost from LiteLLM's pricing map), memory_* counters, router_backend/router_intent, pii extras.

## Tracing (LangSmith)
- Architect requests emit a LangSmith RunTree when LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY is set; runs land in the LANGCHAIN_PROJECT project.
- The eval pipeline builds on the same integration; see docs/langsmith_test_plan.md.

## Database
- SQLite by default; configure DB_URL for other engines.
- Local DB files are ignored by Git; do not commit audit.db or journals.

## Retention
- Script: scripts/sweep_retention.py
- Usage: python scripts/sweep_retention.py
- Recommended to run periodically (cron/k8s job) depending on policy.
