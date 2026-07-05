"""LLM client: LiteLLM-backed with offline stub fallback, audit metadata included."""
import os
from typing import Any, Dict, List, Optional

from app.utils.logger import get_logger

# LLM client backed by LiteLLM for all real providers, with a safe offline
# stub by default. Returns a structured dict with text and audit metadata
# (tokens + real per-model cost_usd from LiteLLM's pricing map). When a
# provider fails or is not configured, it falls back to the deterministic
# stub to keep tests stable.


class LLMClient:
    """LiteLLM wrapper with configurable provider/model and offline fallback."""
    def __init__(self):
        self.provider = (os.getenv("LLM_PROVIDER", "stub") or "stub").lower()
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        try:
            self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))
        except Exception:
            self.temperature = 0.0
        try:
            self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "512"))
        except Exception:
            self.max_tokens = 512
        self._logger = get_logger("llm")

    def _stub_call(
        self, messages: List[Dict[str, str]], reason: Optional[str] = None
    ) -> Dict[str, Any]:
        if reason:
            self._logger.warning(
                "LLM fallback to stub",
                extra={
                    "extra": {
                        "provider": self.provider,
                        "model": self.model,
                        "reason": reason,
                    }
                },
            )
        prompt = "\n".join(
            m.get("content", "") for m in messages if m.get("role") != "system"
        )
        text = "[stub] This is a deterministic offline response. " + (
            prompt[:200] if isinstance(prompt, str) else ""
        )
        # Deterministic token estimates
        tp = max(1, len(prompt.split()))
        tc = max(1, min(self.max_tokens, len(text.split())))
        return {
            "text": text,
            "provider": "stub",
            "model": self.model,
            "tokens_prompt": tp,
            "tokens_completion": tc,
            "cost_usd": 0.0,
        }

    def _litellm_model(self, model: str) -> str:
        """Map provider + model to a LiteLLM model string."""
        if "/" in model:
            return model
        if self.provider == "azure":
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or model
            return f"azure/{deployment}"
        if self.provider == "openai":
            return model
        return f"{self.provider}/{model}"

    def call(
        self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Call LLM via LiteLLM; return (text, provider, model, tokens, cost_usd) or stub on failure."""
        provider = self.provider
        model_to_use = model or self.model
        if provider == "stub":
            return self._stub_call(messages, reason="provider=stub configured")
        try:
            import litellm

            params: Dict[str, Any] = {
                "model": self._litellm_model(model_to_use),
                "messages": messages,
                "max_tokens": self.max_tokens,
                # LiteLLM silently drops params a given model doesn't support
                # (e.g. temperature on reasoning models).
                "drop_params": True,
            }
            if self.temperature not in (None, 0.0):
                params["temperature"] = self.temperature
            resp = litellm.completion(**params)

            text = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            tp = getattr(usage, "prompt_tokens", 0) or 0
            tc = getattr(usage, "completion_tokens", 0) or 0

            # Real per-model cost from LiteLLM's bundled pricing map.
            try:
                cost = float(litellm.completion_cost(completion_response=resp))
            except Exception:
                try:
                    pc, cc = litellm.cost_per_token(
                        model=params["model"],
                        prompt_tokens=tp,
                        completion_tokens=tc,
                    )
                    cost = float(pc) + float(cc)
                except Exception:
                    cost = 0.0

            return {
                "text": text,
                "provider": provider,
                "model": getattr(resp, "model", None) or model_to_use,
                "tokens_prompt": tp,
                "tokens_completion": tc,
                "cost_usd": cost,
            }
        except Exception as e:
            # Missing keys, unknown providers, and provider errors all land
            # here: fall back to the deterministic stub with diagnostics.
            return self._stub_call(messages, reason=f"{provider} error: {e}")
