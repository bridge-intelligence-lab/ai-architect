import os
from typing import Any, Dict, List, Optional

from app.utils.logger import get_logger

# Provider-agnostic LLM client with safe offline stub by default.
# Returns a structured dict with text and audit metadata. When providers fail
# or are not configured, it falls back to a deterministic stub to keep tests stable.


class LLMClient:
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

    def _stub_call(self, messages: List[Dict[str, str]], reason: Optional[str] = None) -> Dict[str, Any]:
        if reason:
            self._logger.warning(
                "LLM fallback to stub", extra={"extra": {"provider": self.provider, "model": self.model, "reason": reason}}
            )
        prompt = "\n".join(m.get("content", "") for m in messages if m.get("role") != "system")
        text = (
            "[stub] This is a deterministic offline response. "
            + (prompt[:200] if isinstance(prompt, str) else "")
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

    def call(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        provider = self.provider
        model_to_use = model or self.model
        if provider == "stub":
            return self._stub_call(messages, reason="provider=stub configured")
        try:
            if provider == "openai":
                from openai import OpenAI  # type: ignore

                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return self._stub_call(messages, reason="missing OPENAI_API_KEY")
                client = OpenAI(api_key=api_key)
                params: Dict[str, Any] = {
                    "model": model_to_use,
                    "messages": messages,
                    "max_completion_tokens": self.max_tokens,
                }
                # Some newer models only allow default temperature; omit when 0.0/None
                if self.temperature not in (None, 0.0):
                    params["temperature"] = self.temperature
                try:
                    resp = client.chat.completions.create(**params)
                except Exception as e:
                    # If temperature caused a 400, retry once without it
                    msg = str(e)
                    if "temperature" in msg and "unsupported" in msg.lower() and "temperature" in params:
                        params.pop("temperature", None)
                        resp = client.chat.completions.create(**params)
                    else:
                        raise
                choice = resp.choices[0]
                text = getattr(choice.message, "content", "") or ""
                tp = getattr(resp.usage, "prompt_tokens", None) or 0
                tc = getattr(resp.usage, "completion_tokens", None) or 0
                # Cost estimation is provider/model specific; best-effort zero unless configured elsewhere
                return {
                    "text": text,
                    "provider": provider,
                    "model": model_to_use,
                    "tokens_prompt": tp,
                    "tokens_completion": tc,
                    "cost_usd": 0.0,
                }
            if provider == "openrouter":
                import requests  # type: ignore

                api_key = os.getenv("OPENROUTER_API_KEY")
                if not api_key:
                    return self._stub_call(messages, reason="missing OPENROUTER_API_KEY")
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model_to_use,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
                r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=30)
                try:
                    data = r.json()
                except Exception:
                    return self._stub_call(messages, reason=f"openrouter HTTP {r.status_code}")
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                tp = usage.get("prompt_tokens", 0)
                tc = usage.get("completion_tokens", 0)
                return {
                    "text": text,
                    "provider": provider,
                    "model": model_to_use,
                    "tokens_prompt": tp,
                    "tokens_completion": tc,
                    "cost_usd": 0.0,
                }
            if provider == "azure":
                # Azure OpenAI compatible API
                import requests  # type: ignore

                api_key = os.getenv("AZURE_OPENAI_API_KEY")
                endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
                deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or model_to_use
                if not api_key or not endpoint:
                    return self._stub_call(messages, reason="missing AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT")
                url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview"
                headers = {
                    "api-key": api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
                r = requests.post(url, json=payload, headers=headers, timeout=30)
                try:
                    data = r.json()
                except Exception:
                    return self._stub_call(messages, reason=f"azure HTTP {r.status_code}")
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                tp = usage.get("prompt_tokens", 0)
                tc = usage.get("completion_tokens", 0)
                return {
                    "text": text,
                    "provider": provider,
                    "model": deployment or model_to_use,
                    "tokens_prompt": tp,
                    "tokens_completion": tc,
                    "cost_usd": 0.0,
                }
        except Exception as e:
            # Last resort: stub with diagnostics
            return self._stub_call(messages, reason=f"{provider} error: {e}")
        # Unknown provider -> stub
        return self._stub_call(messages, reason="unknown provider")
