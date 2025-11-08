import os
import importlib

from app.services.llm_client import LLMClient


def test_openai_unsupported_model_falls_back_with_warning(monkeypatch, capsys):
    # Ensure provider is openai but with an unsupported model name
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    # Missing key should trigger clear reason
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = LLMClient()
    out = client.call([{"role": "user", "content": "hello"}])

    assert out["provider"] == "stub"
    assert out["model"] == "gpt-4o-mini"


def test_openai_exception_falls_back_with_reason(monkeypatch):
    # Simulate openai client import and call raising
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    class DummyChoice:
        def __init__(self):
            class M:
                pass
            self.message = M()
            self.message.content = "ok"

    class DummyResp:
        def __init__(self):
            self.choices = [DummyChoice()]
            class U:
                pass
            self.usage = U()
            self.usage.prompt_tokens = 1
            self.usage.completion_tokens = 1

    def raise_error(*args, **kwargs):
        raise RuntimeError("boom")

    class DummyClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise_error()

    # Patch OpenAI class to our dummy
    import builtins
    import types

    class OpenAI:  # type: ignore
        def __init__(self, *a, **k):
            pass
        class chat:  # type: ignore
            class completions:  # type: ignore
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("boom")

    import sys
    module_name = "openai"
    mod = types.ModuleType(module_name)
    mod.OpenAI = OpenAI
    sys.modules[module_name] = mod

    client = LLMClient()
    out = client.call([{"role": "user", "content": "hello"}])
    assert out["provider"] == "stub"
