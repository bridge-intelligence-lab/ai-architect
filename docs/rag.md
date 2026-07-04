# Retrieval Configuration

## Two retrieval backends

`app/services/doc_retriever.py` is the retrieval facade. `RAG_BACKEND`
selects the backend:

1. **`keyword_scan` (default).** Deterministic keyword scan: the question is
   normalized into terms (stopwords removed, domain terms like `gdpr`/`pii`
   preserved), every `.md`/`.txt` file under `DOCS_PATH` is scored by term
   overlap, and top files come back as citations with 200-character
   snippets. No embeddings, no vector store, no LLM calls, so tests and CI
   stay reproducible and offline.
2. **`vector`.** Chroma-backed semantic retrieval
   (`app/services/vector_retriever.py`): document chunks are ingested into
   a persistent Chroma collection by `scripts/ingest_docs.py` and queried
   by cosine similarity over the configured embeddings. If the vectorstore
   is missing or empty, retrieval falls back to the keyword scan, and the
   result reports the backend actually used.

In both cases the answer is extractive, composed from the returned
snippets. When nothing matches, citations are empty and the answer says so;
no placeholder content is fabricated.

## Ingestion (vector backend)

1. Place `.md`/`.txt`/`.pdf` files under `DOCS_PATH`
2. Run `python scripts/ingest_docs.py` or `make ingest` (chunks of 1000 chars
   with 200 overlap; idempotent, ids derive from path + offset; files in
   `RAG_EXCLUDE_FILES` are skipped)
3. Set `RAG_BACKEND=vector` and query with `grounded=true`

## Environment flags

- `RAG_BACKEND=keyword_scan|vector` (default: `keyword_scan`)
- `DOCS_PATH` — corpus root. Careful: the keyword-scan query path defaults to
  `./examples` while `scripts/ingest_docs.py` defaults to `./docs`; set it
  explicitly so both paths agree
- `RAG_EXCLUDE_FILES` — comma-separated basenames never used as grounding
  context. The default excludes the eval/test-prompt docs (they contain the
  eval questions verbatim and would otherwise be retrieved as "context" for
  them). Enforced at all three paths: keyword scan, vector query (over-fetches
  2x then drops excluded chunks, so an already-built store behaves), and
  ingestion
- `VECTORSTORE_PATH=./.local/vectorstore` — Chroma persistence dir
- `RAG_COLLECTION=docs` — Chroma collection name
- `EMBEDDINGS_PROVIDER=local|hash|stub` — `local` uses
  sentence-transformers (`LOCAL_EMBEDDING_MODEL`, default all-MiniLM-L6-v2);
  `hash` is a deterministic hashed bag-of-words used by CI golden-query
  tests (offline, no model download); `stub` is the legacy length-based
  stub (degenerate for ranking, kept for compatibility)
- `RAG_MULTI_QUERY_ENABLED=false`, `RAG_MULTI_QUERY_COUNT=3`,
  `RAG_HYDE_ENABLED=false` — deterministic query-expansion flags
  (keyword-scan path)

The audit record reports `rag_backend` as the backend actually used
(`keyword_scan` or `vector`). The query-expansion flags are reported only when
the keyword-scan path runs (they are no-ops under `vector`).

## Testing

`tests/test_vector_rag.py` holds golden-query tests: a small corpus is
ingested with `EMBEDDINGS_PROVIDER=hash` and each query must rank its
expected source first, plus determinism, fallback, and empty-corpus
contracts. Keep new tests offline; never depend on a model download.

## See also

- `rag_vector_backends.md`: backend matrix and planned managed backends
- `ports_and_adapters.md`: RAGPort design and how backends plug in
- `docs/adr/0005-doc-retriever-naming.md`: why the module was renamed
