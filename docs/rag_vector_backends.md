---
title: RAG Vector Backends
status: current
module: rag
last_reviewed: 2026-07-04
source:
  - app/services/vector_retriever.py
---

# RAG Vector Backends

## Today

- Default: deterministic keyword scan (`RAG_BACKEND=keyword_scan`) for
  CI/local reproducibility.
- Real vector retrieval: Chroma (embedded, persistent) via
  `RAG_BACKEND=vector`, implemented in `app/services/vector_retriever.py`.
  See `rag.md` for flags, ingestion, and fallback behavior.
- Embeddings: `EMBEDDINGS_PROVIDER=local|hash|stub`. `local` uses
  sentence-transformers; `hash` is the deterministic offline provider used
  by golden-query tests.

There is no LangChain in the retrieval path; the old
`LC_RAG_BACKEND`/`LC_VECTOR_BACKEND` flags never existed in code and are
gone from the docs.

## Pinecone (planned)

Goal: drop-in managed alternative to Chroma for scale/HA.

- Proposed env flags:
  - `VECTOR_BACKEND=pinecone` (default `chroma`)
  - `PINECONE_API_KEY=...`
  - `PINECONE_INDEX_NAME=ai-architect`
  - optional `PINECONE_NAMESPACE=default`
- Behavior: with `RAG_BACKEND=vector` and `VECTOR_BACKEND=pinecone`,
  initialize Pinecone with the configured embedder. If credentials are
  missing or init fails, fall back to Chroma; if Chroma is unavailable,
  fall back to the keyword scan.
- Migration steps: introduce `VECTOR_BACKEND` in `vector_retriever.py`,
  extend `scripts/ingest_docs.py`, add a diagnostic to report
  collection/index counts per backend.

## Operational notes

- Local/dev/test: keyword scan or Chroma; zero ops, fully offline with
  `EMBEDDINGS_PROVIDER=hash`.
- Production: consider Pinecone once wired; watch index size and cost; use
  namespaces for multi-tenant.

## Safety and fallbacks

- All vector backends are optional; the app must keep operating on the
  keyword scan when flags, stores, or credentials are missing.
- Tests stay deterministic and offline by default (no model downloads, no
  network).
