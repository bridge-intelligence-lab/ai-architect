# Capabilities Roadmap (Planning)

Purpose and principles
- Provide a vendor‑neutral, actionable plan for advanced capabilities.
- Principles: deterministic by default (CI offline), ports‑and‑adapters, privacy‑first, observability built‑in, graceful fallbacks.

How to use this roadmap
- For each capability: define value, ports/interfaces, options, phased plan, success metrics, dependencies, fallbacks, and ADR triggers.
- Keep domain‑specific examples generic (e.g., “time‑series signals” or “sequential decision‑making”).

1) Protocols and interop
- Value: low‑latency, language‑agnostic clients; interactive sessions.
- Ports/Interfaces: gRPC services for Query/Predict/Architect (unary + stream), WebSockets for bi‑directional chat; interceptors for auth/trace.
- Options: grpcio + grpc-gateway; FastAPI WebSockets; SSE remains for simplicity.
- Phases:
  - P0: proto contracts; SSE contract documented (exists), WS/grpc design.
  - P1: minimal gRPC server with Query unary + stream; WS for Architect.
  - P2: metadata propagation, tracing; gateway/ingress.
- Success: p95 latency under target; feature parity with REST; robust cancellation.
- ADRs: gRPC service design; WebSockets event model.

2) Feature store and data quality
- Value: consistent online/offline features; reduce training‑serving skew.
- Ports: FeatureStorePort; QualityCheckPort.
- Options: Feast (online/offline), sqlite/parquet default; Great Expectations or Soda.
- Phases:
  - P0: design doc + schemas (FeatureRow) (ingestion_pipelines.md covers); minimal local store.
  - P1: batch writer/reader, predict‑time lookup; basic expectations.
  - P2: online store adapter (Redis/sql); freshness/TTL; skew checks.
- Success: feature hit ratio > 99% in tests; freshness SLO; expectation pass rate.
- ADRs: feature store selection; expectation policy (block vs warn).

3) Vector backends and hybrid search
- Value: scalable retrieval; portability.
- Ports: VectorStorePort; EmbeddingsPort (exists conceptually).
- Options: FAISS/Chroma default; pgvector, Qdrant, Weaviate, Milvus; hybrid BM25 + dense; rerankers.
- Phases:
  - P0: adapter design; deterministic fallback retained.
  - P1: FAISS/Chroma adapters; environment selection; idempotent upserts.
  - P2: pgvector/Qdrant + reranker.
- Success: retrieval quality on golden queries; ingestion idempotency; latency SLOs.
- ADRs: backend choices; migration strategy.

4) Model adaptation and serving performance
- Value: align models with domain; improve latency/cost.
- Ports: AdapterLoaderPort; ServingPort.
- Options: PEFT/LoRA/QLoRA; vLLM/TensorRT‑LLM; OpenAI/Azure/AWS endpoints.
- Phases:
  - P0: adapter loading design, registry link; prompt registry remains default.
  - P1: PEFT adapter load for local HF model; eval gates; rollback.
  - P2: acceleration backend integration (vLLM/TensorRT‑LLM).
- Success: quality uplift vs baseline; latency/cost reductions.
- ADRs: adapter loading strategy; eval/rollback policy.

5) Sequential decision‑making (generic)
- Value: adapt retrieval/tool choices and resources under uncertainty.
- Ports: PolicyPort; FeedbackPort.
- Options: contextual bandits for reranking/query reformulation/tool selection; offline evaluation first; online shadow.
- Phases:
  - P0: logging and feedback schema; offline evaluator.
  - P1: bandit policy selection for retrieval options; shadow only.
  - P2: guarded online with kill switches.
- Success: improved metrics (citation correctness, cost, latency) on A/B; safe rollback.
- ADRs: policy selection scope; metrics and guardrails.

6) Ingestion (reference)
- Value: scalable streaming/batch; deterministic CI.
- Ports: SourcePort, StreamBusPort, ComputePort, FeatureStorePort, VectorStorePort, MetadataStorePort, OrchestratorPort (see ingestion_pipelines.md).
- Phases: per ingestion_pipelines.md (P1 docs → P4 optional integrations).
- Success: idempotent upserts; measurable lag and error budgets.
- ADRs: ingestion architecture (ADR 0002 exists), adapters as needed.

7) Observability and tracing
- Value: diagnose latency/cost/hallucination/drift fast; correlate across services.
- Ports: TracePort; Metrics registry; Log sink.
- Options: OpenTelemetry; LangSmith; Prometheus/Grafana (exists); structured logs (exists).
- Phases:
  - P0: trace design with context propagation; sampling plan.
  - P1: basic traces for LLM calls and RAG; link request_id.
  - P2: spans across gRPC/WebSockets and ingestion stages.
- Success: end‑to‑end trace coverage > 80% in staging; low overhead.
- ADRs: tracing backend and sampling policy.

8) Security and governance
- Value: safe multi‑tenant operation and compliance.
- Ports: AuthZPort (OPA/Cerbos), SecretsPort (KMS/Vault), RetentionPort.
- Options: OPA/Cerbos; Vault/KMS; encrypted vector stores; DP options.
- Phases:
  - P0: policy model and data classification.
  - P1: ABAC with OPA/Cerbos; secrets via local env for dev.
  - P2: retention/delete semantics across memory/vector stores.
- Success: policy coverage; least privilege; retention verified in tests.
- ADRs: ABAC engine; data retention model.

9) Evaluation and feedback
- Value: measurable quality and safe iteration.
- Ports: EvalPort; FeedbackPort.
- Options: golden sets; citation correctness; hallucination metrics; Argilla/Label Studio.
- Phases:
  - P0: offline eval harness spec; minimal golden sets.
  - P1: online A/B and shadow harness with guardrails.
  - P2: human feedback loop.
- Success: CI eval gates; online improvements without regressions.
- ADRs: metric definitions; promotion criteria.

10) Deployment and DevX
- Value: reproducible deployments and smooth developer experience.
- Ports: CLI; IaC; CodegenPort.
- Options: Helm/TF; OpenAPI/proto codegen; Make targets; local sandbox.
- Phases:
  - P0: CLI plan and minimal commands; proto/OpenAPI codegen guidance.
  - P1: Helm chart and TF modules; CI/CD pipelines for models/data/prompts.
  - P2: chaos/resilience testing playbooks.
- Success: time‑to‑deploy and MTTR reductions; developer onboarding speed.
- ADRs: infra stack choices; codegen tooling.

Planning board (draft)
- P0 (docs/design): 1,2,3,4,5,6,7,8,9,10
- P1 (minimal adapters/POCs): 1(gRPC/WS), 2(local feature store + expectations), 3(FAISS/Chroma), 4(adapter load), 6(local batch/stream scripts), 7(traces for LLM/RAG)
- P2 (scale/backends): 1(gateway, metadata), 2(online store), 3(pgvector/Qdrant + rerank), 4(vLLM/TensorRT‑LLM), 6(bus adapters + DLQ), 7(distributed traces)

Notes
- Keep domain‑specific RL or finance‑related examples out of public docs; use generic terms like “sequential decision‑making.”
- Raise ADRs per capability when design choices solidify.
