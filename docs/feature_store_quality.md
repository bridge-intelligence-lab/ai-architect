# Feature Store and Data Quality (Vendor‑Neutral)

Purpose
- Provide a clear, vendor‑neutral blueprint for online/offline feature storage, point‑in‑time (PIT) correctness, freshness/TTL, and quality checks.
- Keep deterministic defaults for CI with graceful fallbacks when optional infrastructure isn’t configured.

Goals and non‑goals
- Goals
  - Consistent features across streaming (online) and batch (offline) without training‑serving skew.
  - Point‑in‑time correctness and late‑arrival handling.
  - Freshness and TTL guarantees with observability.
  - Quality checks (schema/range/nullness/staleness/drift) with policy (warn|block).
- Non‑goals
  - Requiring heavy infra by default. The local setup uses Parquet/SQLite and remains deterministic.

Core concepts and schemas (logical)
- Entity: { entity_id, description?, metadata? }
- FeatureSet: { name, version, entities: [Entity], schema, freshness_ttl_sec, offline_table?, online_store? }
- FeatureRow: { entity_id, event_time, feature_set, version, values: {k: v}, write_time, content_hash }
- PIT join rules
  - Training: join labels to features using event_time with look‑back windows; no leakage from the future.
  - Serving: select the most recent FeatureRow at or before the request time; enforce freshness_ttl_sec.
- Late events and corrections
  - Late FeatureRows are upserted by (entity_id, event_time, feature_set, version). Consumers may recompute aggregates or mark corrections.

Ports and adapters (design)
- FeatureStorePort
  - write_online(entity_id, rows) → upsert by composite key; returns upsert_count, freshness stats
  - read_online(entity_id, as_of_time, feature_set, version) → FeatureRow or None
  - write_offline(table_ref, rows) → append (idempotent by content_hash)
  - read_offline(query) → iterator/batches
  - capabilities() → { online: true|false, ttl_supported: true|false, pit_supported: true|false }
- QualityCheckPort
  - validate(feature_rows, suite) → { passed: bool, violations: [...], metrics: {...} }
  - suites: schema, ranges, nullness, uniqueness, staleness, window_fill, drift (PSI/KS)
- Default adapters
  - LocalFeatureStore: offline Parquet (or SQLite) + simple online SQLite (or in‑proc cache), enabled with env only.
  - No‑op QualityCheck (warn only) by default; optional Great Expectations/Soda adapter later.
- Optional adapters
  - FeastFeatureStore: maps to Feast online/offline stores while keeping FeatureStorePort contracts.

Ingestion flows (reuse ingestion_pipelines.md)
- Streaming
  1) Signals → compute windowed features (sliding/tumbling/EWMA/z‑score). 
  2) Quality checks (warn|block by policy). 
  3) Upsert to online (exactly‑once by key); append to offline (Parquet) for PIT training.
  4) Record freshness (now − event_time) and staleness metrics.
- Batch
  1) Historical download → normalize → compute features using the same codepath as streaming. 
  2) Write to offline store and optionally materialize recent slices to online. 
  3) Maintain checkpoints and content_hash for idempotency.

Predict integration (design)
- Extend /predict semantics (no breaking change):
  - If payload contains { entity_id, feature_set?, version? }, the service first attempts online lookup:
    • hit: fills the feature vector in expected order; audit fields include feature_store_backend, online_hit=true, feature_freshness_seconds, feature_set_version
    • miss: fallback to payload.features (current behavior), audit online_hit=false
  - Optional skew check: when both payload.features and store values are present, compute simple diffs and record skew_check_result in audit.
  - Enforce freshness_ttl_sec: stale reads can WARN or BLOCK by QUALITY_POLICY.

Data quality checks (examples)
- Schema: features present with expected types; unknowns flagged.
- Ranges: numeric bounds; categorical domains.
- Nullness: missing rate below threshold; no NaNs in required features.
- Uniqueness: (entity_id, event_time, feature_set, version) uniqueness.
- Staleness: freshness ≤ freshness_ttl_sec; histogram of freshness.
- Window fill: expected observation count per window (time‑series signals).
- Drift: PSI/KS versus reference windows (e.g., last week vs. baseline).
- Policy: QUALITY_POLICY=warn|block (default warn in dev/CI). Blocked requests return 422/400 with audit fields set.

Observability
- Metrics (suggested)
  - feature_store_online_hit_total{feature_set,version}
  - feature_store_latency_seconds{op: read|write}
  - feature_freshness_seconds histogram
  - feature_upserts_total{status}
  - expectations_failed_total{suite}
  - staleness_violations_total
- Logs: structure with entity_id, feature_set, version, request_id; summarize violations.

Configuration (env)
- FEATURE_STORE_BACKEND=local|feast (default: local or disabled)
- FEATURE_SET and FEATURE_SET_VERSION default for /predict when not provided in payload
- FEATURE_FRESHNESS_TTL_SEC for serving; QUALITY_POLICY=warn|block
- OFFLINE_DATA_PATH and OFFLINE_FORMAT=parquet|delta; ONLINE_DB_URL (sqlite:///… by default) or Redis URL (optional)
- QUALITY_EXPECTATIONS_PATH to point to Checks (optional)

Rollout plan
- P0: this document; align with ingestion_pipelines.md.
- P1: local feature store spec (Parquet + SQLite) and example expectation suites in docs (no strict dependency). Predict integration design prepared.
- P2: optional Feast adapter; enable online lookup in /predict (env‑gated) with audit fields and metrics. Implement QUALITY_POLICY behavior.
- P3: lineage hooks (OpenLineage/DataHub), drift dashboards, advanced skew checks.

Security and privacy
- Apply PII redaction policies before persisting features. 
- Enforce RBAC/ABAC for write/read APIs; avoid leaking sensitive attributes.
- Retention and delete semantics for online/offline stores.

Testing strategy (future work)
- PIT joins correctness with golden data; late events corrections.
- Freshness TTL enforcement and metrics.
- Online hit/miss and fallback behavior under QUALITY_POLICY.
- Expectation suites pass/fail behaviors without external infra (use local adapters).

Feast adapter — initial plan (docs only)
- Adapter scope
  - Map FeatureStorePort to Feast APIs for offline (historical) and online (low-latency) reads/writes.
  - Keep deterministic defaults: when Feast is not configured, fall back to LocalFeatureStore.
- Minimal repo layout
  - feature_repo/
    • feature_store.yaml (registry config)
    • entities.py (Entity definitions)
    • feature_views.py (FeatureView definitions for pilot sets)
- Online store: Redis recommended (dev/staging); offline store: Parquet/Delta; registry: local file.
- CI/dev posture: adapter is env-gated; tests use LocalFeatureStore.

Pilot FeatureSets (proposed)
- price_features_v1 (time-series signals)
  - Entity: asset_id (string)
  - Features (all float unless noted):
    • return_1s, return_5s, return_60s
    • ewma_5s, ewma_60s
    • rolling_vol_60s
    • zscore_60s
    • momentum_60s
  - TTL/freshness: 5–10 seconds for 1s windows; 60–120 seconds for 60s windows (tunable)
  - PIT rule: serve the latest row at or before request_time; allow late corrections within WATERMARK_SECONDS
  - Offline table: offline/price_features/v1 (partitioned by date/hour)
  - Online store key: (asset_id)
- session_user_features_v1 (demo)
  - Entity: user_id (string)
  - Features: page_views_5m (int), events_5m (int), dwell_time_avg_5m (float), last_active_ts (timestamp)
  - TTL/freshness: 5 minutes
  - Offline table: offline/session_user_features/v1

Decision points (to confirm during implementation)
- Online store default for local runs: SQLite vs Redis (recommended: Redis for realistic latency; SQLite for pure local/offline).
- Offline format: Parquet now; Delta optional when Spark available.
- QUALITY_POLICY defaults: warn in dev/CI; block in production for staleness > TTL.
- Feature windows and TTLs for pilot FeatureSets (see above as starting values).

Observability additions (for adapter)
- feature_store_backend: local|feast in audits
- feature_store_online_hit_total with labels {feature_set, version}
- feature_freshness_seconds histogram per feature_set

See also
- ingestion_pipelines.md — streaming and batch design
- mlops_plan.md — drift and model lifecycle
- capabilities_current.md, capabilities_roadmap.md — context and planning
