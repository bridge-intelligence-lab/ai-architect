"""FinOps cost wiring: real per-model cost_usd via LiteLLM's pricing map."""

import litellm

from app.services.llm_client import LLMClient
from app.utils.cost import cost_for_tokens, estimate_tokens_and_cost


def test_llm_call_reports_real_cost(monkeypatch):
    # Route through LiteLLM with a mocked response (no network); cost must
    # come from the pricing map, not a hardcoded zero.
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    real_completion = litellm.completion

    def _mocked(**params):
        return real_completion(
            model=params["model"],
            messages=params["messages"],
            mock_response="Hello from mocked provider",
        )

    monkeypatch.setattr(litellm, "completion", _mocked)

    out = LLMClient().call([{"role": "user", "content": "hello there"}])
    assert out["provider"] == "openai"
    assert out["tokens_prompt"] > 0
    assert out["tokens_completion"] > 0
    expected = cost_for_tokens(
        "gpt-4o-mini", out["tokens_prompt"], out["tokens_completion"]
    )
    assert expected is not None and expected > 0
    assert out["cost_usd"] > 0
    assert abs(out["cost_usd"] - expected) < 1e-9


def test_stub_cost_is_zero(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    out = LLMClient().call([{"role": "user", "content": "hello"}])
    assert out["cost_usd"] == 0.0


def test_estimator_uses_litellm_pricing():
    tp, tc, cost = estimate_tokens_and_cost(
        model="gpt-4o-mini", prompt="p" * 400, completion="c" * 400
    )
    pc, cc = litellm.cost_per_token(
        model="gpt-4o-mini", prompt_tokens=tp, completion_tokens=tc
    )
    assert cost == float(pc) + float(cc)
    assert cost > 0


def test_estimator_unknown_model_uses_fallback_table():
    tp, tc, cost = estimate_tokens_and_cost(
        model="totally-unknown-model", prompt="p" * 400, completion="c" * 400
    )
    # falls back to the gpt-4o-mini illustrative row
    assert cost == (tp / 1000.0) * 0.15 + (tc / 1000.0) * 0.60
