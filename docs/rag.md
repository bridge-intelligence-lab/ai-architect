# Retrieval and RAG Configuration

Overview
- The project supports two retrieval paths:
  1) Deterministic retriever (default in tests/CI): scans DOCS_PATH files and merges snippets for reproducible citations with no network calls.
  2) LangChain retriever (opt-in for local/prod): persistent vector store with embeddings (Chroma by default), powered by scripts/ingest_docs.py.
- Tests are written to be deterministic by default; production setups may enable LangChain.

Key environment flags
- LC_RAG_BACKEND=deterministic|langchain (default: deterministic for CI stability)
- DOCS_PATH=./docs (or another folder with .md/.txt/.pdf)
- VECTORSTORE_PATH=./.local/vectorstore (Chroma persistence when using LangChain)
- EMBEDDINGS_PROVIDER=stub|local|openai (stub/local recommended for determinism)
- RAG_MULTI_QUERY_ENABLED=false (experimental; defaults shown)
- RAG_MULTI_QUERY_COUNT=3
- RAG_HYDE_ENABLED=false

Today’s defaults
- Deterministic retriever is the default to keep tests and local dev reproducible.
- If you explicitly set LC_RAG_BACKEND=langchain, Chroma is used by default for persistence.

Ingestion workflow (LangChain mode)
1) Place .md/.txt/.pdf files under DOCS_PATH
2) Run: `python scripts/ingest_docs.py`
3) Start the API: `uvicorn app.main:app --reload`
4) Query with grounding and expect citations when relevant: see docs/api.md or README for curl examples.

Determinism notes
- CI and unit tests assume deterministic retrieval; avoid changing defaults that would fetch embeddings over the network.
- If credentials or vector stores are missing in LangChain mode, the system should gracefully fall back to deterministic retrieval.

Roadmap and backends
- For Pinecone and other managed vector DBs, see rag_vector_backends.md for the plan and additional env flags (LC_VECTOR_BACKEND=pinecone, etc.).

See also
- ports_and_adapters.md: RAGPort design, backends, capabilities, and fallbacks
- related_projects.md: ecosystem projects (LangChain, LlamaIndex, Haystack, SK) and how we integrate
