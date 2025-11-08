# ADR 0002: Ingestion Architecture for Streaming and Batch

Status: Accepted
Date: 2025-10-12

Context
- The project needs scalable ingestion for two broad classes of data:
  1) Document corpora for RAG (chunk, embed, index, update idempotently)
  2) Time‑series signals for near‑real‑time feature generation and offline experimentation
- The current codebase includes a minimal ingest_docs.py validator and deterministic RAG retrieval, but no general ingestion framework or scheduler examples.
- We want to retain vendor neutrality while enabling optional integrations (e.g., Spark/Databricks) without changing endpoint contracts.

Decision
- Adopt a vendor‑neutral, ports‑and‑adapters ingestion design supporting both streaming and batch:
  - SourcePort, StreamBusPort, ComputePort, EmbeddingsPort, VectorStorePort, FeatureStorePort (optional), MetadataStorePort, OrchestratorPort, TracePort
  - Idempotent upserts using content hashes and composite keys; DLQ for failures
  - Streaming: at‑least‑once with partitioning by entity/document identifiers, bounded concurrency, backpressure, watermarking for out‑of‑order events
  - Batch: incremental reprocessing via content hashes/etags, checkpoints for resumability, shared transforms with streaming to avoid skew
  - Orchestration: examples for Airflow and Prefect; cron fallback
  - Observability: metrics for throughput, lag, errors, and latency; structured logs; optional tracing
  - Optional mapping to Spark/Databricks as an implementation of ComputePort/MetadataStorePort, keeping core neutral

Rationale
- Ports isolate core logic from specific libraries/services, enabling progressive adoption and replacement without contract changes.
- Idempotent patterns and DLQs provide resilience under retries and replays.
- Shared transform codepaths eliminate training‑serving skew between streaming and batch features.
- Scheduling examples lower the barrier for productionization across different environments.

Options considered
- Directly coupling to a specific vendor stack (e.g., managed vector DB + managed streaming): rejected due to lock‑in and poor testability.
- Only batch (no streaming): rejected for near‑real‑time use cases.
- Only streaming (no batch): rejected because experimentation and backfills need batch.

Consequences
- Slightly higher up‑front complexity in defining ports and state tables, repaid by flexibility and testability.
- Requires careful defaults to remain deterministic in CI (stub embeddings, local queues, SQLite state).
- Clear path to scale with Kafka/NATS, Spark, and feature/vector stores when configured.

Follow‑up
- Implement CLI scaffolding for batch and stream workers with deterministic defaults.
- Add optional adapters (Kafka/NATS/Pulsar; SQLite/Postgres metadata; FAISS/Chroma vector stores).
- Provide Airflow and Prefect skeletons with comments and example envs.

References
- docs/ingestion_pipelines.md
- docs/ports_and_adapters.md
- docs/capabilities_current.md
