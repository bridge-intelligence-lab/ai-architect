# Getting Started

This guide helps you install, run, and explore AI Architect locally. For a product overview, see the root README. For deeper topics, see the docs index.

Prerequisites
- Python 3.11+
- Optional: Docker (for the observability stack)
- Optional: jq (for scripts/e2e examples)

Quickstart (local)
```bash
# 0) Clone & env
git clone https://github.com/rodrigo-fonseca-oliveira/ai-architect
cd ai-architect
cp .env.example .env  # fill in only if using hosted LLMs; local defaults work

# 1) Create virtualenv and install
python -m venv .venv
. .venv/bin/activate
pip install -e .

# 2) (Optional) Ingest docs for RAG (LangChain mode)
# Place .md/.txt/.pdf into DOCS_PATH (defaults to ./docs)
python scripts/ingest_docs.py

# 3) Run API
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4) Sanity checks
curl -s localhost:8000/healthz
curl -s -X POST localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What is GDPR?","grounded": false}' | jq .
```

Architect UI
- Unified UI at http://localhost:8000/ui
- Architect-first experience with streaming and debug panel

RAG basics
- Default in tests/CI: deterministic retriever (no embeddings network calls)
- To use LangChain locally: set LC_RAG_BACKEND=langchain and run scripts/ingest_docs.py
- See docs/rag.md and docs/rag_vector_backends.md for flags and backends

Observability stack (optional)
```bash
docker compose up --build
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

Testing
```bash
make venv
make test
```

Troubleshooting
- Missing citations in deterministic mode: ensure DOCS_PATH points to your docs folder and files are .md/.txt/.pdf
- Vector store not found in LangChain mode: check VECTORSTORE_PATH and re-run scripts/ingest_docs.py
- Protected endpoints (RBAC): use X-User-Role: analyst for grounded /query and admin-only routes

LiteLLM gateway (OpenAI-compatible)
- To route LLM calls via LiteLLM, set:
  - LLM_PROVIDER=openai
  - OPENAI_BASE_URL=http://<your-litellm-host>:<port>/v1
  - LLM_API_KEY=<token-if-required>
  - LLM_MODEL=<alias-configured-in-LiteLLM>
  - EMBEDDINGS_PROVIDER=openai (if embeddings proxied)
  - EMBEDDINGS_MODEL=<embeddings-alias>
- Docker Compose snippet:
  services:
    app:
      environment:
        - LLM_PROVIDER=openai
        - OPENAI_BASE_URL=http://litellm:4000/v1
        - LLM_API_KEY=sk-litellm-any
        - LLM_MODEL=gpt-4o-mini
        - EMBEDDINGS_PROVIDER=openai
        - EMBEDDINGS_MODEL=text-embedding-3-small

Next steps
- Explore the API: docs/api.md
- Learn the architecture: docs/architecture_index.md
- Configure RAG: docs/rag.md
- Review launch details: docs/ai-architect-launch.md
