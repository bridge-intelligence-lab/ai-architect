# Component map

- app/routers/query.py: core /query with router integration and RAG wiring
- app/services/doc_retriever.py: retrieval/citations and RAG flags propagation
- app/services/router.py: rules v2 backend, ENV-configurable
- app/routers/pii.py, app/services/pii_detector.py: PII detection logic and endpoint
- app/routers/risk.py, app/services/risk_scorer.py: Risk endpoint and heuristic scorer
- app/routers/research.py: Research agent endpoint
- app/routers/memory_short.py, app/routers/memory_long.py: memory endpoints
- app/utils/rbac.py: roles, grounded policy
- app/utils/audit.py, db/: audit rows and DB session helpers
- scripts/ingest_docs.py: ingestion of docs corpus
- docs/: user and system documentation
