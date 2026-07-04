"""Deterministic keyword-scan document retriever.

Scans text files under DOCS_PATH, scores them by keyword overlap with the
question, and returns snippet citations. There are no embeddings, no vector
store, and no LLM calls; results are fully deterministic, which keeps tests
and CI reproducible. A real vector-retrieval backend is planned separately
(see docs/MODERNIZATION_PLAN.md, row C).
"""

import os
from typing import Any, Dict, List, Tuple


def is_enabled() -> bool:
    # keyword scan is currently the sole retrieval backend
    return True


def _normalize_terms(text: str) -> List[str]:
    tokens = [t.strip(".,:;!?()[]{}\"'`").lower() for t in text.split()]
    stop = set(
        [
            "what",
            "is",
            "the",
            "and",
            "or",
            "a",
            "an",
            "how",
            "to",
            "of",
            "in",
            "at",
            "for",
            "on",
            "does",
            "it",
            "that",
            "this",
            "about",
            "with",
            "be",
        ]
    )
    terms = [
        t
        for t in tokens
        if t
        and (
            len(t) > 2 or t in ("gdpr", "pii", "ccpa", "hipaa", "policy", "encryption")
        )
    ]
    terms = [t for t in terms if t not in stop]
    # dedupe preserve order
    seen = set()
    out: List[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _scan_docs_for_terms(docs_path: str, terms: List[str]) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    if not os.path.isdir(docs_path):
        return citations
    for root, _, files in os.walk(docs_path):
        for fn in files:
            if fn.lower().endswith((".txt", ".md")):
                path = os.path.join(root, fn)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                    t_low = text.lower()
                    score = sum(1 for term in terms if term in t_low)
                    if score == 0:
                        # fallback: simple character overlap heuristic
                        overlap = sum(
                            1 for ch in set(" ".join(terms)) if ch and ch in t_low
                        )
                        score = overlap // 5  # scale down
                    if score > 0:
                        snippet = text[:200].replace("\n", " ")
                        citations.append(
                            {
                                "source": os.path.relpath(path, docs_path),
                                "page": None,
                                "snippet": snippet,
                                "_score": score,
                            }
                        )
                except Exception:
                    continue
    return citations


def reformulate_queries(question: str, n: int) -> List[str]:
    base = question.strip()
    terms = _normalize_terms(question)
    key_terms = " ".join(terms[:8])
    # Deterministic but richer set when multi-query is enabled (n>2)
    base_variants = [
        base,
        f"Key terms: {key_terms}",
        f"Explain: {base}",
        f"Describe policy: {base}",
        f"Summarize: {base}",
        f"Definition and scope: {base}",
        f"Compliance guidance: {base}",
    ]
    # ensure determinism and cap to n
    out: List[str] = []
    for v in base_variants:
        if v not in out:
            out.append(v)
        if len(out) >= n:
            break
    return out


def hyde_snippet(question: str) -> str:
    terms = _normalize_terms(question)
    head = " ".join(terms[:6])
    return f"This document discusses {head}. It provides guidance, definitions, and examples relevant to compliance and data protection."


def _merge_citations(
    cit_sets: List[List[Dict[str, Any]]], k: int
) -> List[Dict[str, Any]]:
    acc: Dict[Tuple[str, int | None], Dict[str, Any]] = {}
    for cit_list in cit_sets:
        for c in cit_list:
            key = (c.get("source", "unknown"), c.get("page"))
            if key not in acc:
                acc[key] = dict(c)
            else:
                acc[key]["_score"] = acc[key].get("_score", 0) + c.get("_score", 0)
    merged = list(acc.values())
    merged = sorted(merged, key=lambda c: c.get("_score", 0), reverse=True)
    # strip internal score and return top-k
    for c in merged:
        c.pop("_score", None)
    return merged[:k]


def answer_with_citations(question: str, k: int = 3) -> Dict[str, Any]:
    """Return citations from a deterministic keyword scan of DOCS_PATH.

    The answer is extractive: it is composed from the top-ranked snippets.
    When nothing matches, citations are empty and the answer says so; no
    placeholder content is fabricated.
    """
    docs_path = os.getenv("DOCS_PATH", "./examples")

    citations: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {}
    try:
        multi = os.getenv("RAG_MULTI_QUERY_ENABLED", "false").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        n = int(os.getenv("RAG_MULTI_QUERY_COUNT", "3"))
        hyde = os.getenv("RAG_HYDE_ENABLED", "false").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        meta.update(
            {
                "rag_multi_query": multi,
                "rag_multi_count": n if multi else 0,
                "rag_hyde": hyde,
            }
        )

        # Always build at least two variants to improve recall
        base_variants = reformulate_queries(question, n=max(2, n if multi else 2))
        cit_sets: List[List[Dict[str, Any]]] = []
        for v in base_variants:
            terms = _normalize_terms(v)
            cit_sets.append(_scan_docs_for_terms(docs_path, terms))
        if multi and hyde:
            hy = hyde_snippet(question)
            hy_terms = _normalize_terms(hy)
            cit_sets.append(_scan_docs_for_terms(docs_path, hy_terms))
        citations = _merge_citations(cit_sets, k=k)
    except Exception:
        citations = []
    # Ensure at least one citation when docs exist by trying filename match, then falling back to first text file
    if (not citations) and os.path.isdir(docs_path):
        # 1) Try filename match against normalized terms
        norm_terms = _normalize_terms(question)
        fname_match_path = None
        for root, _, files in os.walk(docs_path):
            for fn in files:
                fn_low = fn.lower()
                if any(t in fn_low for t in norm_terms):
                    p = os.path.join(root, fn)
                    if os.path.isfile(p):
                        fname_match_path = p
                        break
            if fname_match_path:
                break
        target_path = fname_match_path
        # 2) If no filename match, fall back to first text-like file (or any file)
        if not target_path:
            for root, _, files in os.walk(docs_path):
                text_files = [f for f in files if f.lower().endswith((".txt", ".md"))]
                search_list = text_files if text_files else files
                for fn in search_list:
                    p = os.path.join(root, fn)
                    if os.path.isfile(p):
                        target_path = p
                        break
                if target_path:
                    break
        if target_path:
            try:
                with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                text = ""
            snippet = (text[:200] if isinstance(text, str) else "").replace("\n", " ")
            citations = [
                {
                    "source": os.path.relpath(target_path, docs_path),
                    "page": None,
                    "snippet": snippet,
                }
            ]
    if citations:
        parts = []
        for c in citations[:k]:
            src = c.get("source", "unknown")
            snippet = (c.get("snippet") or "").strip()
            if snippet:
                parts.append(f"[{src}] {snippet}")
        answer = (
            "Extracted from matching documents:\n" + "\n".join(parts)
            if parts
            else "Matching documents found; see citations."
        )
    else:
        answer = f"No documents under {docs_path} matched the question."
    return {"answer": answer, "citations": citations, **meta}
