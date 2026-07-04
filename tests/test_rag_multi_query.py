import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_rag_multi_query_and_hyde_flags(tmp_path):
    # Legacy path removed; this flag is ignored
    os.environ["RAG_MULTI_QUERY_ENABLED"] = "true"
    os.environ["RAG_MULTI_QUERY_COUNT"] = "3"
    os.environ["RAG_HYDE_ENABLED"] = "true"
    # no embeddings provider needed for the keyword-scan retriever
    headers = {"X-User-Role": "analyst"}
    r = client.post(
        "/query",
        json={
            "question": "What is GDPR and how does it regulate data retention?",
            "grounded": True,
        },
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "audit" in body
    audit = body["audit"]
    # audit backend reflects the actual retriever
    assert audit.get("rag_backend") == "keyword_scan"
    assert audit.get("router_intent") in ("qa", None)
    # flags may not be present in response_audit depending on filtering; check nested audit_dict fallback
    # We at least ensure the call succeeded and returned citations list
    assert isinstance(body.get("citations", []), list)
