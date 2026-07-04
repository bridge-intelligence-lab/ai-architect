# Retrieval Configuration

## What exists today

There is one retrieval path: a deterministic keyword scan implemented in
`app/services/doc_retriever.py` (renamed from `langchain_rag.py`, which never
used LangChain).

How it works:

1. The question is normalized into keyword terms (stopwords removed,
   domain terms like `gdpr`/`pii` preserved).
2. Every `.md`/`.txt` file under `DOCS_PATH` is scanned and scored by term
   overlap.
3. Top-scoring files are returned as citations with a 200-character snippet.
4. The answer is extractive, composed from the returned snippets. When
   nothing matches, citations are empty and the answer says so; no
   placeholder content is fabricated.

There are no embeddings, no vector store, and no LLM calls in this path.
That is deliberate for now: results are fully deterministic, which keeps
tests and CI reproducible and offline.

## Environment flags

- `DOCS_PATH=./docs` — corpus root (`.md`/`.txt`; `scripts/ingest_docs.py`
  can extract text from PDFs)
- `RAG_MULTI_QUERY_ENABLED=false` — expand the question into deterministic
  variants before scanning
- `RAG_MULTI_QUERY_COUNT=3` — number of variants when enabled
- `RAG_HYDE_ENABLED=false` — add a deterministic hypothetical-snippet variant

These flags are propagated into the audit record (`rag_multi_query`,
`rag_multi_count`, `rag_hyde`), and the audit reports
`rag_backend=keyword_scan`.

## What is planned

Real vector retrieval (sentence-transformers embeddings + Chroma behind a
`RAG_BACKEND` flag, with the keyword scan kept as the deterministic
fallback) is row C of [MODERNIZATION_PLAN.md](MODERNIZATION_PLAN.md). Until
that lands, this repo does not do semantic retrieval, and docs should not
claim it does. See `rag_vector_backends.md` for the backend plan.

## See also

- `ports_and_adapters.md`: RAGPort design and how backends will plug in
- `docs/adr/0005-doc-retriever-naming.md`: why the module was renamed
