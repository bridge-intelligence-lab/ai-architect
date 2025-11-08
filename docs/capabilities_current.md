# Current Capabilities (Baseline)

This document captures what is implemented today in AI Architect so we can design new capabilities in isolation on top of a clear baseline.

Overview
- API-first FastAPI service with deterministic defaults (no network in tests) and graceful fallbacks
- Core features: Query + RAG, Architect agent (+SSE and UI), Research agent, Policy Navigator, PII detection and remediation, Risk scoring, Predict (MLflow), Memory (short/long), Metrics and Auditing
- RBAC and PII safety, request-id logging, cost/tokens estimation, structured audits stored in a local DB by default

Endpoints and behaviors
- GET /healthz — liveness check
- GET /metrics — Prometheus metrics; open when METRICS_TOKEN unset, token-protected when set
- POST /query
  - Intents: auto|qa|pii_detect|risk_score (router optional; default falls back to qa)
  - grounded=true: RAG path with citations; records rag flags (multi_query, hyde)
  - ungrouded (or grounded with optional LLM): optional LLM synthesis when LLM_ENABLE_QUERY=true
  - Audit: tokens/cost estimates, router_backend and router_intent, rag_backend ("langchain" today), PII extras when pii_detect intent
- POST /architect (requires PROJECT_GUIDE_ENABLED=true)
  - Structured plan generation via Architect Agent when LLM_ENABLE_ARCHITECT=true
  - When grounded, uses same RAG path for citations
  - Audit includes LLM metadata (provider/model/tokens/cost) and RAG flags when present
- GET /architect/stream — Server-Sent Events (SSE)
  - Events: meta, summary, steps, flags, citations, feature, audit
  - meta includes provider/model/grounded_used; includes memory_* reads when enabled
- GET /architect/ui and GET/POST /ui — HTML UI for Architect/Query/Research
- POST /research — agent pipeline with steps [search, fetch, summarize, risk_check]; per-step RBAC
  - Flags: AGENT_LIVE_MODE, AGENT_URL_ALLOWLIST, DENYLIST (used for risk_check)
  - Audit: step entries with inputs/outputs preview and latency
- POST /policy_navigator — decomposes question, retrieves citations, and synthesizes a recommendation
  - Flags: POLICY_NAV_ENABLED (default true), POLICY_NAV_MAX_SUBQS
- POST /pii — deterministic PII detection (regex + heuristics), optional grounded citations
  - Request: {text, types?, grounded?}; Response: summary, entities, counts, types_present, audit
  - Env: PII_TYPES, PII_LOCALES override active detectors
- POST /pii_remediation — synthesizes remediation suggestions for detected PII
  - Flags: PII_REMEDIATION_ENABLED (default true), PII_REMEDIATION_INCLUDE_SNIPPETS
- POST /predict and GET /predict/schema — MLflow-backed predictions
  - Loads latest run or explicit MLFLOW_MODEL_URI; optional feature_order.json drives schema and enforcement
  - Audit includes model_run_id, model_uri, experiment name, tokens/cost estimates
- POST /risk — heuristic scorer with optional ML-style path
  - Flags: RISK_ML_ENABLED, RISK_THRESHOLD

RAG (grounding) baseline
- Implementation: app/services/langchain_rag.py
  - Deterministic local-docs scanning; honors flags:
    - RAG_MULTI_QUERY_ENABLED (with RAG_MULTI_QUERY_COUNT)
    - RAG_HYDE_ENABLED
  - Uses DOCS_PATH (falls back to ./examples or ./docs)
  - Ensures at least one citation via filename/text fallbacks or synthetic context
  - Returns {answer, citations, rag_multi_query, rag_multi_count, rag_hyde}

Memory
- Short-term (SQLite file, default disabled)
  - Env: MEMORY_SHORT_ENABLED, MEMORY_DB_PATH, MEMORY_SHORT_MAX_TURNS, SHORT_MEMORY_RETENTION_DAYS, SHORT_MEMORY_MAX_TURNS_PER_SESSION
  - Endpoints: GET/DELETE /memory/short, GET /memory/status
  - In-query behavior: prepends recent turns/summary; writes user+assistant turns; summary maintained when turns exceed threshold
  - Audit counters when enabled: memory_short_reads, memory_short_writes, summary_updated, memory_short_pruned
- Long-term (in-process semantic fact store, default disabled)
  - Env: MEMORY_LONG_ENABLED, MEMORY_LONG_RETENTION_DAYS, MEMORY_LONG_MAX_FACTS, MEMORY_COLLECTION_PREFIX
  - Endpoints: GET/DELETE /memory/long, GET /memory/long/export, POST /memory/long/import, GET /memory/status
  - In-query and in-architect behaviors: retrieve facts to augment context; ingest long sentences/facts after responses
  - Audit counters when enabled: memory_long_reads, memory_long_writes, memory_long_pruned

Observability and auditing
- Middleware attaches request_id (header REQUEST_ID_HEADER, default X-Request-ID) and records per-request metrics
- Prometheus metrics (app/utils/metrics.py):
  - app_requests_total{endpoint,status}, app_request_latency_seconds{endpoint}
  - app_tokens_total{endpoint}, app_cost_usd_total{endpoint}
- Structured audits are persisted via db.session and db.models.Audit
  - Every major endpoint writes audit rows best-effort with request id, hashes, latency, token/cost estimates, and feature-specific extras

Security, RBAC, and PII
- Roles: guest < analyst < admin (app/utils/rbac.py)
- Per-endpoint role policies enforced in routers
- PII detection/remediation is local and deterministic by default; PII_TYPES and PII_LOCALES allow runtime configuration
- Denylist for /query research safety checks via DENYLIST

MLflow predict path
- Configuration: MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME
- Optional artifacts:
  - Model path: MLFLOW_MODEL_ARTIFACT_PATH (default "model")
  - Feature order artifact: MLFLOW_FEATURE_ORDER_ARTIFACT (default "feature_order.json")
- /predict/schema exposes the expected features (when artifact present) and run metadata
- /predict enforces exact feature keys when feature order is available and converts numeric-like values

Key components (pointers)
- app/main.py — middleware, router wiring, exception handlers
- app/routers/*.py — endpoints (query, architect, architect_stream, architect_ui, research, policy, predict, pii, pii_remediation, risk, memory, metrics, ui)
- app/services/*.py — RAG, LLM client, MLflow client, PII detector, policy navigator, risk scorer, architect agent
- app/memory/*.py — short_memory (sqlite), long_memory (in-memory + embeddings)
- db/models.py, db/session.py — audit table and DB helpers
- docs/*.md — user/system documentation, prompts/*.yaml — agent prompt specs

Configuration highlights (env)
- PROJECT_GUIDE_ENABLED, LLM_ENABLE_ARCHITECT, LLM_ENABLE_QUERY, LLM_PROVIDER, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS
- DOCS_PATH, RAG_MULTI_QUERY_ENABLED, RAG_MULTI_QUERY_COUNT, RAG_HYDE_ENABLED
- MEMORY_* flags as above
- ROUTER_ENABLED, ROUTER_BACKEND (rules|builtin)
- DB_URL, METRICS_TOKEN, REQUEST_ID_HEADER, DENYLIST
- MLFLOW_* variables as above
- POLICY_NAV_ENABLED, POLICY_NAV_MAX_SUBQS
- PII_REMEDIATION_ENABLED, PII_REMEDIATION_INCLUDE_SNIPPETS, PII_TYPES, PII_LOCALES

Out of scope (to design next, separately)
- PEFT/LoRA/QLoRA fine-tuning and adapter loading
- RLHF/DPO and bandit-based routing
- MCP server/client and tool adapters
- gRPC + streaming RPCs and WebSockets
- Streaming and batch ingestion pipelines; schedulers (Airflow/Prefect)
- Feature store (Feast) and data quality (Great Expectations) with lineage (OpenLineage/DataHub)
- Vector DB backends and hybrid search; rerankers
- OpenTelemetry tracing, semantic caching, cost governance, multi-tenant isolation
