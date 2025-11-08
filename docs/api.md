# API Overview

This service is a FastAPI application for AI risk, compliance, and observability.

- Interactive API docs (Swagger UI): http://localhost:8000/docs
- Alternative docs (ReDoc): http://localhost:8000/redoc
- OpenAPI spec (exported): docs/openapi.yaml (see scripts/export_openapi.py)

## Cross-cutting behavior

- Request ID
  - Each request receives a request ID. By default, it is generated server-side.
  - Override header name via REQUEST_ID_HEADER (default: X-Request-ID).
  - Response includes the same header and logs include request_id.

- Error responses (JSON)
  - All errors use a consistent JSON shape:
    {
      "status": <int>,
      "error": <string>,
      "detail": <any>,
      "request_id": <string|null>
    }
  - Examples:
    - 422 Validation Error
      {
        "status": 422,
        "error": "Validation error",
        "detail": [{"loc": ["body", "field"], "msg": "...", "type": "..."}],
        "request_id": "..."
      }
    - 403 Forbidden
      {
        "status": 403,
        "error": "forbidden",
        "detail": "forbidden",
        "request_id": "..."
      }

- RBAC
  - Header: X-User-Role with one of: guest, analyst, admin (default: guest if missing/unknown).
  - Route-level rules (summary):
    - /metrics: open by default; if METRICS_TOKEN is set, requires header X-Metrics-Token. See observability_metrics.md for details.
    - /predict: analyst/admin
    - /query: grounded=true requires analyst/admin; grounded=false allows guest.
    - /research: step-based rules
      - fetch/search/summarize: analyst+
      - risk_check: guest+

## Notable endpoints

- GET /healthz — liveness probe
- GET /metrics — Prometheus metrics (optionally token-protected)
- POST /predict — model inference; requires role analyst/admin
  - Request: { features: object, user_id?: string }
  - Rules: features must be a non-empty object with numeric-like values; exact feature set must match training
  - Errors: 400 when features invalid/mismatch or when no model is available
  - Notes: training is required first (see docs/ml.md); the server reorders inputs to the training feature order
- GET /predict/schema — returns expected feature list and model metadata (analyst/admin)
  - Response: { features: [string], run_id: string, experiment: string }
  - Notes: Artifacts names configurable via MLFLOW_MODEL_ARTIFACT_PATH and MLFLOW_FEATURE_ORDER_ARTIFACT; MLFLOW_MODEL_URI can override model selection; MLFLOW_MODEL_CACHE_TTL enables in-process caching.
- POST /query

Request: { question: str, grounded?: bool, user_id?: str, session_id?: str, intent?: str }
  - Response: { answer, citations?, audit }
  - Notes: session_id enables short-term memory grouping when MEMORY_SHORT_ENABLED=true
  - Config: ROUTER_ENABLED (intent routing)
- POST /risk — Risk scoring endpoint (analyst/admin)
  - Request: { text: string }
  - Response: { label: "low|medium|high", value: number in [0,1], rationale: string, audit: { ... } }
  - Feature flags:
    - RISK_ML_ENABLED (default: false) — when true, uses a deterministic pseudo-ML path
    - RISK_THRESHOLD (default: 0.6) — classification threshold for ML path
  - Behavior:
    - Default is heuristic scoring based on risk keywords; audit.risk_score_method == "heuristic"
    - When ML is enabled, audit.risk_score_method == "ml" and label/value are derived from the pseudo-ML signal
  - Audit enrichment:
    - audit.risk_score_label, audit.risk_score_value, audit.risk_score_method
- POST /policy_navigator — Policy Navigator Agent (analyst/admin) — Policy Navigator Agent (analyst/admin)
  - Request: { question: string, max_subqs?: number }
  - Response: { recommendation: string, citations: [{source, snippet, page?}], audit: { steps[] } }
- POST /pii_remediation — PII Remediation Agent (analyst/admin)
  - Request: { text: string, return_snippets?: boolean, grounded?: boolean }
  - Response: { remediation: [...], citations?: [...], audit: { pii_entities_count, pii_types } }

- GET /memory/short — list short-term memory for a session (analyst/admin)
  - Params: user_id (required), session_id (required)
  - Response: { turns: [{role, content, timestamp}], summary: string|null, audit: {...} }
- DELETE /memory/short — clear short-term memory for a session (analyst/admin)
  - Params: user_id (required), session_id (required)
  - Response: { cleared: boolean, audit: {...} }
- GET /memory/long — list long-term facts (analyst/admin)
  - Params: user_id (required), q (optional)
  - Response: { facts: [{text, created_at?, metadata?}], audit: {..., memory_long_reads?, memory_long_pruned?} }
- DELETE /memory/long — clear long-term facts for user (analyst/admin)
  - Params: user_id (required)
  - Response: { cleared: boolean, audit: {...} }
- GET /memory/long/export — export long-term facts (analyst/admin)
  - Params: user_id (required)
  - Response: { facts: [{id, text, created_at, metadata, embedding_present, embedding_dim}], audit: {..., memory_long_reads?, memory_long_pruned?} }
- POST /memory/long/import — import long-term facts (analyst/admin)
  - Params: user_id (required)
  - Body: { facts: [{ text: string, metadata?: object }] }
  - Response: { imported: number, audit: {..., memory_long_writes?, memory_long_pruned?} }
- GET /memory/status — memory status (admin only)
  - Response: { config: {...}, short_memory: { sessions: [{user_id, session_id, turns, summary}], db_ok }, long_memory: { users: [{user_id, facts}], store_ok }, counters: { memory_short_pruned_total, memory_long_pruned_total }, audit: {...} }

- /query audit includes memory counters when flags enabled:
  - memory_short_reads, memory_short_writes, summary_updated, memory_short_pruned
  - memory_long_reads, memory_long_writes, memory_long_pruned

  - Feature flags:
    - ROUTER_ENABLED: routes intents (qa, pii_detect, risk_score, other) using simple rules
  - Request fields:
    - question: string (min 3)
    - grounded: boolean (default false)
    - user_id: optional string
    - intent: optional ("auto"|"qa"|"pii_detect"|"risk_score"|"other"); default "auto"
- POST /research — multi-step research pipeline with auditing; step RBAC applies
  - Request: { topic: string, steps?: ["search","fetch","summarize","risk_check"], user_id?: string }
  - Response: { findings: [...], sources: [...], steps: [{name,inputs,outputs,latency_ms,hash,timestamp}], audit: {...} }
  - Defaults: steps defaults to [search, fetch, summarize, risk_check]
  - Flags: AGENT_LIVE_MODE, AGENT_URL_ALLOWLIST, DENYLIST
  - See docs/agents.md for step details

## Router Agent

- Feature-flag: ROUTER_ENABLED (default false)
- Intent options: qa | pii_detect | risk_score | other
- Behavior when enabled:
  - If intent not provided or set to "auto", the router picks an intent using simple rules (see docs/agents.md).
  - For qa + grounded=true, RAG citations are returned via the LC-backed path (default).
- Audit enrichment: router_backend and router_intent are included in the /query response audit field.
- When intent=pii_detect, the answer summarizes detections and the audit includes pii_entities_count, pii_types, and pii_counts.

## Architect

- POST /architect (requires PROJECT_GUIDE_ENABLED=true)
  - Request: { question: string (min 3), grounded?: boolean|null, user_id?: string, session_id?: string }
  - Response: { answer: string, citations?: [Citation], suggested_steps?: [string], suggested_env_flags?: [string], audit: {...}, suggest_feature?: bool, feature_request?: object }
  - Flags: PROJECT_GUIDE_ENABLED, LLM_ENABLE_ARCHITECT, DOCS_PATH, RAG flags
- GET /architect/stream (SSE)
  - Content-Type: text/event-stream
  - Event contract: see docs/agents.md (Architect Agent)
- GET /architect/ui
  - Content-Type: text/html

See docs/agents.md for details on SSE events and flags.
