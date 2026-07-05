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

## Design

**Owns:** the append-only record of what the system did per request.
`write_audit(db, **fields)` in `app/utils/audit.py` plus the `Audit` model in
`db/models.py`; `make_hash` provides sha256 content hashes so prompts/responses are
attributable without storing raw text in fixed columns.

**Contract:** one audit row per handled request, written best-effort at the end of
the handler. Fixed columns (request_id, endpoint, user_id, created_at, tokens,
cost_usd, latency_ms, compliance_flag, prompt_hash, response_hash) plus
feature-specific extras in the response audit payload.

**Invariants:**
- Auditing never breaks the API: a failed write is logged, rolled back, and the
  response still returns. The audit is an observability guarantee, not a
  transactional one; consumers must not assume 100% coverage under DB failure.
- Rows are append-only in practice: nothing in the app updates or deletes audit
  rows except the retention sweep script.
- Hashes, not payloads, in fixed columns: content is referenced by sha256 so the
  table stays lean and privacy exposure is bounded.

**Why it exists:** the governance story (who did what, at what cost, with which
backend/model/policy inputs) is a first-class product feature, not debug logging.

**Non-goals:** not a metrics system (Prometheus owns aggregates), not tamper-evident
(no signing/chaining), not a transaction log for replay.
