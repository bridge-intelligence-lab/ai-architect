from app.services.llm_client import LLMClient


def test_missing_api_key_falls_back_to_stub(monkeypatch):
    # Provider configured but no credentials: LiteLLM raises client-side
    # (no network) and the client falls back to the deterministic stub.
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = LLMClient()
    out = client.call([{"role": "user", "content": "hello"}])

    assert out["provider"] == "stub"
    assert out["model"] == "gpt-4o-mini"
    assert out["cost_usd"] == 0.0


def test_provider_exception_falls_back_to_stub(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    import litellm

    def _boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(litellm, "completion", _boom)

    client = LLMClient()
    out = client.call([{"role": "user", "content": "hello"}])
    assert out["provider"] == "stub"


def test_unknown_provider_falls_back_to_stub(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    monkeypatch.setenv("LLM_MODEL", "whatever")

    client = LLMClient()
    out = client.call([{"role": "user", "content": "hello"}])
    assert out["provider"] == "stub"
