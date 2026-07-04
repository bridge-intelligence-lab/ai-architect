# RAG Vector Backends (Roadmap + How To)

Today
- Default: Deterministic retriever for CI/local reproducibility.
- Optional: LangChain + Chroma (embedded, persistent).
- Switch using env: `LC_RAG_BACKEND=deterministic|langchain` (default: deterministic).
- Vector store flags (LangChain mode):
  - LC_VECTOR_BACKEND=chroma (default)
  - VECTORSTORE_PATH=./.local/vectorstore
  - DOCS_PATH=./docs

How to use LangChain + Chroma now
1) Set LC_RAG_BACKEND=langchain
2) Optionally set EMBEDDINGS_PROVIDER=local or openai (stub/local recommended for tests)
3) Run `python scripts/ingest_docs.py`
4) Start API and query with grounded=true

Pinecone (planned)
- Goal: drop‑in alternative to Chroma when LC_RAG_BACKEND=langchain for managed scale and HA.
- Proposed env flags:
  - LC_VECTOR_BACKEND=pinecone
  - PINECONE_API_KEY=...
  - PINECONE_ENVIRONMENT=...   # e.g., gcp-starter
  - PINECONE_INDEX_NAME=ai-architect
  - (Optional) PINECONE_NAMESPACE=default
- Behavior:
  - If LC_RAG_BACKEND=langchain and LC_VECTOR_BACKEND=pinecone, initialize Pinecone via LangChain using the configured embedding model.
  - If credentials are missing or init fails, fall back to Chroma; if Chroma is unavailable, fall back to deterministic retriever.

Embeddings
- EMBEDDINGS_PROVIDER=openai|local|stub (default: stub/local for deterministic tests)
- OPENAI_API_KEY=... (required for OpenAI embeddings)
- EMBEDDING_MODEL or LLM_MODEL can be used to select specific models depending on provider.

Operational notes
- Local/dev/test: stay with deterministic or langchain+chroma for zero‑ops.
- Production: consider langchain+pinecone; monitor costs and index sizes; use namespaces for multi‑tenant.

Migration plan (later)
1) Introduce LC_VECTOR_BACKEND with default chroma and optional pinecone.
2) Add Pinecone wiring in app/services/doc_retriever.py behind env flags.
3) Extend scripts/ingest_docs.py to support Pinecone.
4) Provide a diagnostic route or script to list collection/index counts across backends.

Safety and fallbacks
- All backends are optional; the app must continue to operate with deterministic retrieval when flags or credentials are missing.
- Tests remain deterministic by default (no network).
