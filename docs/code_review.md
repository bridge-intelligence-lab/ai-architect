AI Architect — Code Review (Session 1)

Overview and scope
- Purpose: Baseline review of code quality, structure, and doc-to-code alignment. No application code changes in this session.
- Deliverables: This living report, a checklist index, and a baseline test run summary.

Operational notes
- Tests are run via shell with .venv activated: . .venv/bin/activate && pytest -q

Repository map (high level)
- FastAPI app: app/
  - Routers: app/routers/* (query, research, predict, pii, pii_remediation, risk, memory, metrics, architect, architect_stream, architect_ui, policy)
  - Services: app/services/* (doc_retriever, router, llm_client, policy_navigator, architect_agent, architect_schema, pii_detector, pii_remediation, mlflow_client)
  - Utils: app/utils/* (logger, metrics, audit, rbac, cost, prompts, exceptions, retention)
  - Memory backends: app/memory/* (short_memory, long_memory)
  - Schemas: app/schemas/* (research, predict)
  - Entry point: app/main.py
- Persistence: db/* (models, session)
- ML: ml/* (train.py, drift.py, data/*.csv)
- OpenAPI: docs/openapi.yaml (generated via scripts/export_openapi.py)

Testing baseline
- Command: . .venv/bin/activate && pytest -q
- Result: PASS
- Date: 2025-10-07
- Docs: docs/*.md
- Tests: tests/* (broad functional coverage by component and endpoint)

API and behavior alignment checklist (initial)
- Endpoints implemented vs docs/openapi.yaml
  - GET /healthz: implemented (metrics router) — OK
  - GET /metrics: implemented with optional token (X-Metrics-Token) — OK
  - POST /query: implemented — OK
  - POST /research: implemented — OK
  - POST /predict: implemented — OK
  - POST /pii: implemented — OK
  - POST /risk: implemented — OK
  - Memory endpoints (get/delete short, get/delete long, export/import, status): implemented — OK
  - POST /policy_navigator: implemented — OK
  - POST /pii_remediation: implemented — OK
  - Architect/Architect UI/stream endpoints are now present in OpenAPI. Content types adjusted: /metrics -> text/plain; /architect/stream -> text/event-stream — UPDATED

Cross-cutting behavior
- Request ID middleware present; exceptions mapped to JSON via app/utils/exceptions.py — aligns with docs/api.md.
- RBAC: parse_role(header X-User-Role), require_role helper; grounded query requires analyst/admin — aligns with docs/security.md and docs/api.md.
- Observability: Prometheus counters/histograms exposed; /metrics excluded from request counters; optional token — aligns with docs/observability.md.
- Audit trail: db/models.Audit and utils/audit.write_audit used best-effort in routers.

Quality notes (initial scan)
- Error handling: consistent JSON error envelope via exception handlers — good.
- Logging: JSON logger with request_id propagation — good; consider structured fields for key audit extras where relevant.
- Configuration: env-first, flags throughout; sensible defaults; feature flags for router, RAG, LLM, memory — good.
- Security: RBAC enforced across sensitive endpoints; /metrics optional token; no secrets in code — good. Consider rate limiting/abuse guards if exposed publicly.
- Performance: synchronous CPU-bound work mostly light; RAG path uses filesystem scans; long operations (MLflow, vector ops) are not on request path except predict — acceptable for reference implementation.
- Testing: extensive functional tests; includes router rules, RAG flags, metrics, PII, risk, memory, LLM audit, drift, MLflow train — strong coverage by behavior.

Doc vs code drift (current)
- Architect endpoints are present in OpenAPI; content types corrected (/metrics -> text/plain; /architect/stream -> text/event-stream).
- RAG ingestion is a lightweight filesystem scan; docs updated accordingly in RAG section.
- PII: Request-level types override supported via payload.types; locales via env.

Security and privacy posture (initial)
- PII: /pii and /pii_remediation enforce analyst/admin; pii_detector used with best-effort; audit includes counts and types — OK.
- RBAC: step-level checks for /research; grounded queries restricted — OK.
- Retention: memory docs describe env knobs; endpoints expose status and export/import — OK.



Recommendations (priority draft)
- Add architect endpoints to OpenAPI/docs or explicitly mark as experimental in docs.
- Clarify RAG ingestion story in docs (current stub scans DOCS_PATH for .md/.txt and falls back to synthetic citation).
- Consider adding minimal health for DB (e.g., /metrics includes audit DB status gauge) — optional.
- Provide a docker-compose override or Make target to run tests in a container for consistency across machines (optional).

Next steps checklist
- [x] Run full test suite and record baseline in this file.
- [ ] Produce endpoint-by-endpoint delta table (docs vs code) with parameters/status codes.

Session log
- Session 5: Router — audit.router_backend now reflects 'simple' when disabled; docs/tests updated.
- Session 6: Risk — clarified flags (RISK_ML_ENABLED, RISK_THRESHOLD) and audit fields; tests green.
- Session 7: Research — documented steps, flags (AGENT_LIVE_MODE, AGENT_URL_ALLOWLIST, DENYLIST), and per-step RBAC; added allowlist test; tests green.
- Session 9: Architect — documented endpoints, flags, and SSE event contract; added runtime SSE test; tests green.
- Session 10: ML/MLflow — logged model signature and feature order during training; added negative tests for /predict; docs clarified train→predict flow; tests green.
- Session 8: Observability — documented middleware behavior and audit persistence, added test to ensure /metrics isn’t counted; metrics/logging/audit tests green.
