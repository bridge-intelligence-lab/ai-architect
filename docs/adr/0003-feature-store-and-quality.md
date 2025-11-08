# ADR 0003: Feature Store and Data Quality

Status: Proposed
Date: 2025-10-12

Context
- We need consistent online/offline features with point‑in‑time correctness, freshness guarantees, and quality checks.
- Today, /predict accepts raw features and MLflow model loading works, but there’s no feature store or expectation policy integrated.
- We want vendor neutrality by default, with optional adapters to popular systems.

Decision
- Introduce a FeatureStorePort and QualityCheckPort with deterministic local defaults and optional adapters:
  - FeatureStorePort supports online read/write (idempotent upserts) and offline read/write for PIT training.
  - QualityCheckPort supports schema/range/nullness/staleness/drift checks with a policy (warn|block), default warn.
- Ingestion (streaming and batch) uses the same transforms to avoid training‑serving skew; upsert keys are (entity_id, event_time, feature_set, version).
- /predict may perform an online lookup (when entity_id provided) before falling back to payload features; audit fields record store backend, hit/miss, freshness, and version; optional skew checks.
- Keep code vendor‑neutral; provide an optional Feast adapter later without changing endpoint contracts.

Rationale
- Ports and adapters preserve testability and neutrality; deterministic local defaults allow CI to run without external infra.
- Freshness/TTL and PIT correctness are essential for reliable predictions.
- Quality gates improve reliability; warn‑by‑default avoids breaking dev/CI while enabling strict gating in prod.

Alternatives considered
- Bake features directly into the predict payload with no store: simpler but increases skew risk and duplication.
- Hard‑couple to a single feature store: faster initially but harms portability and CI determinism.

Consequences
- Extra surface area (ports, adapters, policies) to maintain, offset by clearer contracts and extensibility.
- Introduces expectation management and potential blocking behavior; needs careful policy defaults.

Follow‑ups
- Specify local adapters (Parquet + SQLite) and sample expectation suites in docs.
- Add metrics for hit/miss, latency, freshness, and violations.
- Implement optional Feast adapter.
- Wire /predict online lookup under an env flag with audit fields and QUALITY_POLICY handling.

References
- docs/feature_store_quality.md
- docs/ingestion_pipelines.md
- docs/capabilities_roadmap.md
