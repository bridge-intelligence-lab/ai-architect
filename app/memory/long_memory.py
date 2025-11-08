import hashlib
import os
from typing import Any, Dict, List

from app.services.rag_retriever import LocalEmbeddings, OpenAIEmbeddings, StubEmbeddings

# Legacy embeddings removed; using simple cosine over in-process store
from app.utils.logger import get_logger

logger = get_logger(__name__)

PREFIX = os.getenv("MEMORY_COLLECTION_PREFIX", "memory")
MEMORY_LONG_RETENTION_DAYS = int(os.getenv("MEMORY_LONG_RETENTION_DAYS", "0"))

# Fallback in-memory store to avoid external dependency in tests/CI
_FACT_STORE: dict[str, list[dict[str, Any]]] = {}


def _get_embedder():
    prov = os.getenv("EMBEDDINGS_PROVIDER", "local").lower()
    if prov == "openai":
        return OpenAIEmbeddings()
    if prov == "stub":
        return StubEmbeddings()
    return LocalEmbeddings()


def retrieve_facts(user_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    # naive similarity via cosine on local embeddings if available
    facts = _FACT_STORE.get(user_id, [])
    if not facts:
        retrieve_facts._last_pruned = 0  # type: ignore[attr-defined]
        return []
    # prune by retention days if configured
    pruned = 0
    retention_days = int(os.getenv("MEMORY_LONG_RETENTION_DAYS", "0"))
    if retention_days and retention_days > 0:
        import time

        cutoff = time.time() - (retention_days * 86400)
        before = len(facts)
        facts = [f for f in facts if f.get("created_at", 0) >= cutoff]
        pruned += before - len(facts)
        _FACT_STORE[user_id] = facts
    emb = _get_embedder()
    try:
        qvec = emb.embed([query])[0]
    except Exception:
        retrieve_facts._last_pruned = pruned  # type: ignore[attr-defined]
        # If embeddings fail, just return recent facts
        return facts[:top_k]

    def cos(a, b):
        import math

        num = sum(x * y for x, y in zip(a, b))
        da = math.sqrt(sum(x * x for x in a))
        db = math.sqrt(sum(y * y for y in b))
        return (num / (da * db)) if da and db else 0.0

    scored = []
    for f in facts:
        vec = f.get("embedding")
        if not vec:
            try:
                vec = emb.embed([f["text"]])[0]
            except Exception:
                vec = None
        score = cos(qvec, vec) if vec else 0.0
        scored.append((score, f))
    scored.sort(key=lambda x: x[0], reverse=True)
    retrieve_facts._last_pruned = pruned  # type: ignore[attr-defined]
    return [f for _, f in scored[:top_k]]


def ingest_fact(
    user_id: str, fact: str, metadata: Dict[str, Any] | None = None
) -> bool:
    emb = _get_embedder()
    try:
        vec = emb.embed([fact])[0]
    except Exception:
        vec = None
    lst = _FACT_STORE.setdefault(user_id, [])
    _id = hashlib.sha256(fact.encode("utf-8")).hexdigest()
    # idempotent upsert by id
    exists = None
    for i, f in enumerate(lst):
        if f.get("id") == _id:
            exists = i
            break
    import time

    item = {
        "id": _id,
        "text": fact,
        "metadata": metadata or {},
        "embedding": vec,
        "created_at": time.time(),
    }
    if exists is not None:
        lst[exists] = item
    else:
        lst.append(item)
    # enforce max facts per user if configured
    max_facts = int(os.getenv("MEMORY_LONG_MAX_FACTS", "0"))
    if max_facts and max_facts > 0 and len(lst) > max_facts:
        # evict oldest by created_at
        before = len(lst)
        lst.sort(key=lambda f: f.get("created_at", 0), reverse=False)
        while len(lst) > max_facts:
            lst.pop(0)
        evicted = before - len(lst)
        try:
            ingest_fact._last_evicted = int(evicted)  # type: ignore[attr-defined]
        except Exception:
            pass
        _FACT_STORE[user_id] = lst
    else:
        try:
            ingest_fact._last_evicted = 0  # type: ignore[attr-defined]
        except Exception:
            pass
    return True


def clear_long_memory(user_id: str) -> None:
    if user_id in _FACT_STORE:
        del _FACT_STORE[user_id]
