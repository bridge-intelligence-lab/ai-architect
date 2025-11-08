# Ingestion Pipelines: Streaming and Batch (Vendor‑Neutral)

Purpose
- Define a scalable, deterministic-by-default ingestion architecture for both document corpora (RAG) and time‑series signals.
- Keep the core design vendor‑neutral via ports and adapters; document an optional mapping to Spark/Databricks without coupling the codebase.

Goals and constraints
- Idempotent: replays and retries must not create duplicates.
- Resilient: backpressure, DLQ, and recovery flows.
- Deterministic by default: CI does not require external infra.
- Unified transforms: the same feature/chunking code paths for streaming and batch to prevent training‑serving skew.
- Observable: clear metrics, logs, and audit trails.

Scope and use cases
- Documents (RAG): ingest .md/.txt/.pdf from FS/object stores; produce chunks and upsert into a vector store; maintain document state for incremental re‑indexing.
- Time‑series signals: ingest append‑only events (e.g., telemetry or sensor‑like signals), compute windowed features, and write to an online/offline store.

Architecture: ports and adapters
- SourcePort: list/read objects from FS/S3/GCS/Azure; HTTP and git optional; CDC (e.g., Debezium) optional.
- StreamBusPort: Kafka/NATS/Pulsar; CloudEvents envelope; in‑memory queue fallback for CI.
- ComputePort: local worker (default); optional Spark/Flink implementations.
- EmbeddingsPort: stub/local/OpenAI; batchable; deterministic stub in CI.
- VectorStorePort: FAISS/Chroma/local backends; optional managed backends later.
- FeatureStorePort (optional): online/offline feature stores (e.g., local sqlite/parquet for default; Feast for larger setups).
- MetadataStorePort: state for documents/chunks/signals (SQLite/Postgres/Delta); idempotency and checkpoints.
- OrchestratorPort: Airflow/Prefect; cron fallback.
- TracePort: no‑op by default; optional OpenTelemetry/LangSmith.

Data model (logical)
- Document: { id, uri, content_hash, etag, version, last_modified, metadata, status, error_count }
- Chunk: { doc_id, chunk_id, offset, length, chunk_hash, text, embedding_ref, created_at }
- Signal (time‑series): { entity_id, event_time, sequence, payload, source, trace_id, content_hash }
- FeatureRow: { entity_id, event_time, window, feature_set, version, values, content_hash }

Idempotency and exactly‑once sinks
- Use content_hash (e.g., sha256) over canonicalized inputs to drive upserts.
- Document upsert key: (doc_id, content_hash); chunk upsert key: (doc_id, chunk_hash).
- Feature upsert key: (entity_id, event_time, feature_set, version).
- Maintain a small state table with last processed content_hash per entity/doc to skip identical replays.

Streaming pipeline (at‑least‑once)
1) Discover/notify: sources emit doc_added/doc_updated/doc_deleted or signal events to StreamBusPort.
2) Fetch/extract: download or read object; for PDFs use extract_pdf_text (deterministic in CI by gating).
3) Normalize: canonicalize text, trim fronts/footers, scrub PII if required.
4) Chunk or Feature: 
   - Docs: chunk_text(size, overlap) → {offset, text}.
   - Signals: compute windowed features (tumbling/sliding/EWMA/z‑score) using watermarking for out‑of‑order events.
5) Embed (docs only): batch embeddings using EmbeddingsPort; drop into VectorStorePort with upsert semantics.
6) Sink and ack: write state rows and emit success/failure events. Failures go to DLQ with full error context.

Partitioning and backpressure
- Partition key: consistent hash of doc_id (docs) or entity_id (signals).
- Concurrency: bounded worker pools per partition; backpressure measured by queue lag.
- Watermarks: discard or hold back late events beyond WATERMARK_SECONDS; optionally emit corrections.

Batch pipeline (incremental and backfills)
1) List objects for a time range or prefix.
2) Compare to MetadataStorePort by etag/content_hash; derive delta set.
3) For each delta: run the same Normalize → Chunk/Feature → (Embed) → Sink stages.
4) Write offline artifacts: Parquet/Delta partitioned by date/entity; register dataset versions.
5) Checkpointing: resume from last processed key or time‑based watermark.

Scheduling
- Airflow DAG (skeleton)
  - Tasks: discover → stage_in → normalize → chunk_or_feature → embed (optional) → index/sink → validate → publish
  - Use task groups for doc vs signal branches; retries with exponential backoff; XCom only for minimal metadata references.
- Prefect Flow (skeleton)
  - Parameterized flow with mapping over items; built‑in retry policies; concurrency limits per partition key.
- Cron fallback: small installs can run batch scripts periodically with file‑based checkpoints.

Observability
- Metrics (suggested):
  - ingestion_docs_total{stage,status,source}
  - ingestion_signals_total{stage,status,source}
  - ingestion_errors_total{stage,reason}
  - ingestion_lag_seconds{source}
  - features_latency_ms{window}
  - dlq_size
- Logs: structured, with correlation id (trace_id) and entity/doc ids; redact payloads by policy.
- Tracing: optional spans around each stage; disabled by default in CI.

Configuration (env suggestions)
- Sources: INGEST_SOURCES, SOURCE_INCLUDE/EXCLUDE globs, SOURCE_POLL_INTERVAL_SEC
- Bus: KAFKA_BROKERS | NATS_URL | PULSAR_URL, TOPIC_DOCS, TOPIC_SIGNALS, TOPIC_DLQ
- Concurrency: STREAM_CONCURRENCY, STREAM_BATCH_SIZE, MAX_EMBED_BATCH
- Watermarks: WATERMARK_SECONDS, LATE_EVENT_POLICY=drop|hold|correct
- Features: FEATURE_WINDOWS="1s,5s,1m", FEATURE_SET_VERSION, EXACTLY_ONCE_SINK=true
- Stores: OFFLINE_DATA_PATH, OFFLINE_FORMAT=parquet|delta, METADATA_DB_URL, VECTORSTORE_BACKEND
- Quality: EXPECTATIONS_PATH (Great Expectations checks) [optional]

Quality and governance
- Input validation at normalize stage; deterministic sampling for QA.
- Optional Great Expectations/Soda checks for schema, ranges, nullness, drift.
- Privacy: PII redaction gates before embedding/indexing.

Rollout plan
- Phase 1: Documentation (this file) and align with ports_and_adapters.md.
- Phase 2: CLI scaffolding:
  - scripts/batch_ingest_docs.py (JSONL/Parquet artifacts, optional local vector store upserts)
  - scripts/stream_worker.py (local dir queue; optional Kafka/NATS if configured)
- Phase 3: Adapters and metrics: add Bus adapters, MetadataStore (SQLite/Postgres), Prom metrics, DLQ handling.
- Phase 4: Optional integrations: Feature store (Feast), lineage (OpenLineage/DataHub), and hybrid/managed vector DBs.

Optional mapping: Spark/Databricks (implementation example)
- Treat Spark Structured Streaming as a ComputePort implementation; Delta as MetadataStorePort/Offline store.
- Autoloader ingests into Bronze; transforms to Silver with chunking/feature UDFs; upsert to Gold (vector/index or features).
- Delta Live Tables for quality thresholds; Jobs/Workflows for scheduling; MLflow ties to models and features.
- Keep code vendor‑neutral; map via environment/config without changing endpoint contracts.

See also
- ports_and_adapters.md: port strategy and adapter selection
- rag.md: retrieval configuration and ingestion workflow for documents
- capabilities_current.md: current runtime features and flags
