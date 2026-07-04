import os
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_query_llm_audit_fields(monkeypatch):
    # Enable LLM for query but monkeypatch client to be deterministic
    monkeypatch.setenv("LLM_ENABLE_QUERY", "true")
    monkeypatch.setenv("ROUTER_ENABLED", "false")
    # Ensure memory is off to avoid modifying prompts
    monkeypatch.setenv("MEMORY_SHORT_ENABLED", "false")
    monkeypatch.setenv("MEMORY_LONG_ENABLED", "false")

    # Stub LLMClient.call
    def _fake_call(self, messages):
        return {
            "text": "Hello from fake LLM",
            "provider": "stub",
            "model": "unit-test",
            "tokens_prompt": 7,
            "tokens_completion": 3,
            "cost_usd": 0.0,
        }

    from app.services import llm_client as llm_mod

    monkeypatch.setattr(llm_mod.LLMClient, "call", _fake_call)

    r = client.post("/query", json={"question": "what is this?", "grounded": False})
    # ensure we used LLM by checking answer text
    assert r.json()["answer"].startswith("Hello from fake LLM")
    assert r.status_code == 200
    data = r.json()
    audit = data["audit"]
    assert audit.get("llm_provider") == "stub"
    assert audit.get("llm_model") == "unit-test"
    assert audit.get("llm_tokens_prompt") == 7
    assert audit.get("llm_tokens_completion") == 3


def test_architect_llm_json_parse_and_fallback(monkeypatch):
    # Enable architect and LLM for it
    monkeypatch.setenv("PROJECT_GUIDE_ENABLED", "true")
    monkeypatch.setenv("LLM_ENABLE_ARCHITECT", "true")
    # Deterministic docs path
    monkeypatch.setenv("DOCS_PATH", os.path.join(os.getcwd(), "e2e_docs"))

    # Fake LLM returning JSON
    def _fake_call_json(self, messages):
        return {
            "text": '{"summary": "ok", "suggested_steps": ["a", "b"], "suggested_env_flags": ["X"]}',
            "provider": "stub",
            "model": "unit-test",
            "tokens_prompt": 5,
            "tokens_completion": 2,
            "cost_usd": 0.0,
        }

    from app.services import llm_client as llm_mod

    monkeypatch.setattr(llm_mod.LLMClient, "call", _fake_call_json)

    r = client.post("/architect", json={"question": "gdpr data retention", "mode": "guide"}, headers={"X-User-Role": "analyst"})
    assert r.status_code == 200
    data = r.json()
    assert data["suggested_steps"] == ["a", "b"]
    assert data["suggested_env_flags"] == ["X"]
    assert data["audit"].get("llm_provider") == "stub"

    # Now make LLM return invalid JSON and ensure fallback structure still present
    def _fake_call_bad(self, messages):
        return {
            "text": "not json",
            "provider": "stub",
            "model": "unit-test",
            "tokens_prompt": 1,
            "tokens_completion": 1,
            "cost_usd": 0.0,
        }

    monkeypatch.setattr(llm_mod.LLMClient, "call", _fake_call_bad)

    r2 = client.post("/architect", json={"question": "custom use case", "mode": "brainstorm"})
    assert r2.status_code == 200
    data2 = r2.json()
    # Ensure lists exist even after fallback
    assert isinstance(data2.get("suggested_steps"), list)
    assert isinstance(data2.get("suggested_env_flags"), list)
