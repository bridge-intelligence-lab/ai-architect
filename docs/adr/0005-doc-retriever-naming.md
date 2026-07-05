---
title: ADR 0005: Rename langchain_rag to doc_retriever; retire placeholder responses
status: current
module: architecture
last_reviewed: 2026-07-05
decision_date: 2026-07-04
adr_status: Accepted
---

# ADR 0005: Rename langchain_rag to doc_retriever; retire placeholder responses

## Context

- `app/services/langchain_rag.py` did not use LangChain. It was (and remains)
  a deterministic keyword/file scan over `DOCS_PATH` that returns snippet
  citations. The module name, its docstrings, and `docs/rag.md` all described
  a LangChain RetrievalQA / Chroma vector path that does not exist in the
  code (`LC_RAG_BACKEND` and `VECTORSTORE_PATH` were documented but read
  nowhere). Names that overstate capability are the most expensive kind of
  debt in a reference repo: reviewers find them fast, and they undermine the
  parts that are genuinely built.
- The retrieval path also fabricated output: `answer_with_citations` always
  returned a hardcoded "This is a stubbed answer..." string, and when no
  document matched it invented a `source: synthetic` citation. The `/query`
  router duplicated that fabrication in a second safety-net block.

## Decision

- Rename `app/services/langchain_rag.py` to `app/services/doc_retriever.py`
  and describe it as what it is: a deterministic keyword-scan retriever.
- Retire the placeholder response paths:
  - The answer is now extractive, composed from the top-ranked snippets; when
    nothing matches, citations are empty and the answer states that.
  - The fabricated `synthetic` citation fallback is removed from both the
    module and the `/query` router (the module's real-file fallbacks remain).
  - The audit field `rag_backend` now reports `keyword_scan` instead of
    `langchain`.
- Rewrite `docs/rag.md` to document only what exists, pointing to
  MODERNIZATION_PLAN row C for the real vector backend.

## Consequences

- API-visible changes: `/query` grounded answers contain extracted snippets
  instead of the stub sentence; `audit.rag_backend` changes value; queries
  with an empty/missing corpus return zero citations instead of a fabricated
  one. Callers that only consume `citations` (architect, PII remediation,
  policy navigator) are unaffected.
- Row C (`feat/vector-rag`) can now introduce a real vector backend behind
  `RAG_BACKEND` without inheriting a misleading module name.
