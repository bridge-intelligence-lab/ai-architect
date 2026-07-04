"""Chroma-backed vector retrieval over ingested document chunks.

Enabled with RAG_BACKEND=vector. Chunks are ingested into a persistent
Chroma collection by scripts/ingest_docs.py; queries embed the question
with the configured provider and return the top-k chunks as citations.

Embedding providers (EMBEDDINGS_PROVIDER):
- local: sentence-transformers (real semantic retrieval; downloads a model)
- hash:  deterministic hashed bag-of-words (offline; used in tests/CI)
- stub:  length-based vectors from rag_retriever (degenerate for ranking;
         kept only for compatibility)

The caller (doc_retriever.answer_with_citations) falls back to the
deterministic keyword scan when this backend is unavailable or empty.
"""

import hashlib
import os
import re
from typing import Any, Dict, List

DEFAULT_COLLECTION = "docs"
HASH_DIM = 384


def vectorstore_path() -> str:
    return os.getenv("VECTORSTORE_PATH", "./.local/vectorstore")


def collection_name() -> str:
    return os.getenv("RAG_COLLECTION", DEFAULT_COLLECTION)


class HashEmbeddings:
    """Deterministic hashed bag-of-words embeddings.

    Tokens are hashed into a fixed number of buckets and counted, so texts
    sharing vocabulary land close under cosine distance. No network, no
    model download; suitable for CI golden-query tests.
    """

    def embed(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for text in texts:
            vec = [0.0] * HASH_DIM
            for tok in re.findall(r"[a-z0-9]+", text.lower()):
                bucket = int(hashlib.md5(tok.encode()).hexdigest(), 16) % HASH_DIM
                vec[bucket] += 1.0
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            out.append(vec)
        return out


def get_embedder():
    provider = os.getenv("EMBEDDINGS_PROVIDER", "local").lower()
    if provider == "hash":
        return HashEmbeddings()
    if provider == "stub":
        from app.services.rag_retriever import StubEmbeddings

        return StubEmbeddings()
    from app.services.rag_retriever import LocalEmbeddings

    return LocalEmbeddings()


def get_collection(create: bool = False):
    import chromadb

    client = chromadb.PersistentClient(path=vectorstore_path())
    if create:
        return client.get_or_create_collection(
            collection_name(), metadata={"hnsw:space": "cosine"}
        )
    return client.get_collection(collection_name())


def is_ready() -> bool:
    """True when a non-empty collection exists at VECTORSTORE_PATH."""
    try:
        return get_collection().count() > 0
    except Exception:
        return False


def query(question: str, k: int = 3) -> List[Dict[str, Any]]:
    """Return top-k chunk citations for the question.

    Raises on any backend failure; the caller decides whether to fall back.
    """
    col = get_collection()
    emb = get_embedder().embed([question])[0]
    res = col.query(
        query_embeddings=[emb],
        n_results=max(1, k),
        include=["documents", "metadatas", "distances"],
    )
    citations: List[Dict[str, Any]] = []
    ids = res.get("ids") or [[]]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    for i in range(len(ids[0])):
        meta = metas[i] if i < len(metas) else {}
        snippet = (docs[i] if i < len(docs) else "")[:200].replace("\n", " ")
        citations.append(
            {
                "source": (meta or {}).get("source", ids[0][i]),
                "page": (meta or {}).get("page"),
                "snippet": snippet,
                "distance": round(dists[i], 4) if i < len(dists) else None,
            }
        )
    return citations
