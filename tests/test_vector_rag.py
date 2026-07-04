import importlib
import os

from fastapi.testclient import TestClient


def _write_corpus(docs_dir):
    docs_dir.mkdir()
    (docs_dir / "gdpr.txt").write_text(
        "GDPR is the European Union regulation on data protection and privacy. "
        "It governs consent, data subject rights, and retention of personal data."
    )
    (docs_dir / "kubernetes.txt").write_text(
        "Kubernetes orchestrates containers across a cluster. Pods, deployments, "
        "and services are the core primitives for scheduling workloads."
    )
    (docs_dir / "mlflow.txt").write_text(
        "MLflow tracks machine learning experiments, logging metrics, parameters, "
        "and artifacts for model training runs."
    )


def _ingest(monkeypatch, tmp_path):
    docs_dir = tmp_path / "docs"
    _write_corpus(docs_dir)
    monkeypatch.setenv("DOCS_PATH", str(docs_dir))
    monkeypatch.setenv("VECTORSTORE_PATH", str(tmp_path / "vec"))
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")  # deterministic, offline
    import scripts.ingest_docs as ingest_docs

    importlib.reload(ingest_docs)
    assert ingest_docs.main() > 0
    return docs_dir


def test_vector_golden_queries(monkeypatch, tmp_path):
    _ingest(monkeypatch, tmp_path)
    monkeypatch.setenv("RAG_BACKEND", "vector")
    from app.services.doc_retriever import answer_with_citations

    golden = {
        "What does GDPR say about data retention?": "gdpr.txt",
        "How does Kubernetes schedule pods in a cluster?": "kubernetes.txt",
        "Where are experiment metrics and artifacts logged?": "mlflow.txt",
    }
    for question, expected_source in golden.items():
        result = answer_with_citations(question, k=2)
        assert result["rag_backend"] == "vector"
        assert result["citations"], question
        assert result["citations"][0]["source"] == expected_source, question
        assert result["answer"].startswith("Extracted from matching documents:")


def test_vector_retrieval_is_deterministic(monkeypatch, tmp_path):
    _ingest(monkeypatch, tmp_path)
    monkeypatch.setenv("RAG_BACKEND", "vector")
    from app.services.doc_retriever import answer_with_citations

    r1 = answer_with_citations("GDPR consent rules", k=3)
    r2 = answer_with_citations("GDPR consent rules", k=3)
    assert r1["citations"] == r2["citations"]


def test_vector_falls_back_to_keyword_scan_when_empty(monkeypatch, tmp_path):
    docs_dir = tmp_path / "docs"
    _write_corpus(docs_dir)
    monkeypatch.setenv("DOCS_PATH", str(docs_dir))
    # point at a vectorstore that was never ingested
    monkeypatch.setenv("VECTORSTORE_PATH", str(tmp_path / "empty-vec"))
    monkeypatch.setenv("RAG_BACKEND", "vector")
    from app.services.doc_retriever import answer_with_citations

    result = answer_with_citations("GDPR data protection", k=3)
    assert result["rag_backend"] == "keyword_scan"
    assert result["citations"]
    assert any("gdpr" in (c["source"] or "").lower() for c in result["citations"])


def test_query_endpoint_reports_vector_backend(monkeypatch, tmp_path):
    _ingest(monkeypatch, tmp_path)
    monkeypatch.setenv("RAG_BACKEND", "vector")
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/query",
        json={"question": "What does GDPR regulate?", "grounded": True},
        headers={"X-User-Role": "analyst"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["audit"].get("rag_backend") == "vector"
    assert len(data.get("citations", [])) >= 1
    assert data["citations"][0]["source"] == "gdpr.txt"


def test_empty_corpus_returns_no_citations(monkeypatch, tmp_path):
    # keyword scan on an empty directory: honest empty result, nothing fabricated
    empty = tmp_path / "empty-docs"
    empty.mkdir()
    monkeypatch.setenv("DOCS_PATH", str(empty))
    monkeypatch.delenv("RAG_BACKEND", raising=False)
    from app.services.doc_retriever import answer_with_citations

    result = answer_with_citations("anything at all", k=3)
    assert result["citations"] == []
    assert result["answer"].startswith("No documents under")
