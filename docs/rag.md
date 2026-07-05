---
title: Retrieval Configuration
status: current
module: rag
last_reviewed: 2026-07-04
source:
  - app/services/doc_retriever.py
  - app/services/vector_retriever.py
  - scripts/ingest_docs.py
---

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
   `RAG_EXCLUDE_FILES` and directories in `RAG_EXCLUDE_DIRS` are skipped).
   Note: ingestion adds/updates but never deletes — after removing or renaming
   docs, wipe `VECTORSTORE_PATH` and re-ingest or stale chunks stay retrievable
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
- `RAG_EXCLUDE_DIRS` — comma-separated directory names excluded the same way
  (default: `worklog`, so dated work records under `docs/worklog/` never enter
  the corpus)
- `VECTORSTORE_PATH=./.local/vectorstore` — Chroma persistence dir
- `RAG_COLLECTION=docs` — Chroma collection name
- `EMBEDDINGS_PROVIDER=openai|local|hash|stub` (recommended: `openai`).
  `openai` uses text-embedding-3-small by default, overridable via
  `OPENAI_EMBEDDING_MODEL`; network-hosted, no local torch worker to swap
  out under memory pressure. `local` uses sentence-transformers
  (`LOCAL_EMBEDDING_MODEL`, default all-MiniLM-L6-v2); works on a well-fed
  host, but a memory-tight worker can silently fall back to stub embeddings
  and collapse retrieval to identical top-k for every query. `hash` is a
  deterministic hashed bag-of-words used by CI golden-query tests (offline,
  no model download); `stub` is the legacy length-based stub (degenerate
  for ranking, kept for compatibility).
- Switching embedder (different vector dimension) invalidates the store;
  wipe `VECTORSTORE_PATH` and re-ingest. Pin `RAG_COLLECTION` to a per-model
  name (e.g. `docs_openai_3_small`) so accidental provider flips do not hit
  a stale collection.
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

## Design

**Owns:** everything between a question and grounding context: backend selection,
corpus exclusion, query expansion, and citation shaping. Nothing else in the app
touches the corpus directly; `answer_with_citations()` in
`app/services/doc_retriever.py` is the single entry point (the facade), used by
/query, both architect backends, and the MCP server.

**Contract:** `answer_with_citations(question, k) -> {answer, citations[],
rag_multi_query?, rag_multi_count?, rag_hyde?}`. Citations carry `source`, optional
`page`, `snippet`, `distance`. Callers may treat an empty citations list as
"ungrounded"; they never receive excluded content.

**Invariants:**
- Exclusion is enforced at all three paths (keyword scan, vector query, ingestion),
  so a stale store cannot leak excluded files: the vector path over-fetches 2x and
  drops excluded chunks post-hoc.
- The vector backend falls back to keyword scan when the store is missing or empty;
  callers never see a hard failure from a missing store.
- Ingestion is add/update only. Deleting or renaming a doc requires wiping
  `VECTORSTORE_PATH` and re-ingesting, or its chunks stay retrievable.
- Determinism: with `RAG_BACKEND=keyword_scan` (the default) retrieval is fully
  deterministic, which is what CI and the offline test suite rely on.

**Why it exists:** grounding quality is the product's main quality lever (measured:
the 2026-07-04 corpus cleanup moved judge groundedness more than any backend
change), so retrieval is centralized where exclusion and fallback rules can be
enforced once and measured.

**Non-goals:** no reranking, no hybrid search, no managed vector DBs (roadmap);
no write access for callers.
