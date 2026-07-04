from typing import Optional, Tuple

# Token counts remain a crude ~4-chars-per-token estimate (good enough for
# request-level accounting of non-LLM endpoints). Prices come from LiteLLM's
# bundled per-model pricing map, so cost_usd tracks real published rates;
# the static table below is only the fallback for unknown models.
FALLBACK_PRICES_PER_1K = {
    "gpt-4o-mini": (0.15, 0.60),  # (prompt, completion) USD per 1k tokens
    "gpt-4.1": (5.0, 15.0),
    "stub": (0.0, 0.0),
}


def cost_for_tokens(model: str, tokens_prompt: int, tokens_completion: int) -> Optional[float]:
    """Real per-model cost from LiteLLM's pricing map; None if unknown."""
    if model == "stub":
        return 0.0
    try:
        import litellm

        pc, cc = litellm.cost_per_token(
            model=model,
            prompt_tokens=tokens_prompt,
            completion_tokens=tokens_completion,
        )
        return float(pc) + float(cc)
    except Exception:
        return None


def estimate_tokens_and_cost(
    model: str, prompt: str, completion: str
) -> Tuple[int, int, float]:
    tp = max(1, len(prompt) // 4)  # crude: ~4 chars per token
    tc = max(1, len(completion) // 4)
    cost = cost_for_tokens(model, tp, tc)
    if cost is None:
        price = FALLBACK_PRICES_PER_1K.get(model, FALLBACK_PRICES_PER_1K["gpt-4o-mini"])
        cost = (tp / 1000.0) * price[0] + (tc / 1000.0) * price[1]
    return tp, tc, cost
