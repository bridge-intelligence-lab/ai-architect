---
title: Getting Started
status: current
module: overview
last_reviewed: 2026-07-04
---

# Getting Started

This guide helps you install, run, and explore AI Architect locally. For a product overview, see the root README. For deeper topics, see the docs index.

## Prerequisites

- Python 3.11+
- Optional: Docker (for the observability stack)
- Optional: jq (for scripts/e2e examples)

## Quickstart (local)

```bash
# 0) Clone & env
git clone https://github.com/bridge-intelligence-lab/ai-architect
cd ai-architect
cp .env.example .env  # fill in only if using hosted LLMs; local defaults work

# 1) Create virtualenv and install
python -m venv .venv
. .venv/bin/activate
pip install -e .

# 2) (Optional) Vector RAG: ingest docs into the Chroma store
# Place .md/.txt/.pdf into DOCS_PATH (ingest defaults to ./docs; note the
# keyword-scan query path defaults to ./examples, so set DOCS_PATH explicitly)
python scripts/ingest_docs.py
# then set RAG_BACKEND=vector in .env to use the ingested store

# 3) Run API
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4) Sanity checks
curl -s localhost:8000/healthz
curl -s -X POST localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What is GDPR?","grounded": false}' | jq .
```

## Architect UI

- Unified UI at http://localhost:8000/ui
- Architect-first experience with streaming and debug panel

## RAG basics

- Default in tests/CI: deterministic keyword-scan retriever (no embeddings network calls)
- For vector retrieval locally: run scripts/ingest_docs.py, then set RAG_BACKEND=vector
- See docs/rag.md and docs/rag_vector_backends.md for flags and backends

## Observability stack (optional)

```bash
docker compose up --build
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3001 (admin/admin; port 3000 is remapped in docker-compose.yml)
```

## Testing

```bash
make venv
make test
```

## Troubleshooting

- Missing citations in deterministic mode: ensure DOCS_PATH points to your docs folder and files are .md/.txt/.pdf (the keyword-scan path defaults to ./examples when DOCS_PATH is unset)
- Vector store not found with RAG_BACKEND=vector: check VECTORSTORE_PATH and re-run scripts/ingest_docs.py (retrieval falls back to keyword scan when the store is missing or empty)
- Protected endpoints (RBAC): use X-User-Role: analyst for grounded /query and admin-only routes

## LLM providers (via LiteLLM)

- All real providers route through the LiteLLM library natively; there is no
  separate gateway to configure. Set:
  - LLM_PROVIDER=openai (or another LiteLLM-supported provider; `stub` = offline default)
  - LLM_MODEL=<model name, e.g. gpt-4.1-mini>
  - OPENAI_API_KEY=<your key> (provider keys are read by LiteLLM at call time)
- Embeddings are configured separately: EMBEDDINGS_PROVIDER=local|openai|hash|stub,
  with LOCAL_EMBEDDING_MODEL (default all-MiniLM-L6-v2) or OPENAI_EMBEDDING_MODEL
  (default text-embedding-ada-002)
- Per-request cost comes from LiteLLM's pricing map and lands in audit rows and /metrics

## Next steps

- Explore the API: docs/api.md
- Learn the architecture: docs/architecture_index.md
- Configure RAG: docs/rag.md
