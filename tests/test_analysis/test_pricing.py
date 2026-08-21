from src.analysis.pricing import estimate_cost_usd


def test_returns_zero_for_free_gemma_model():
    assert estimate_cost_usd("gemma-4-26b-a4b-it", 1_000_000, 1_000_000) == 0.0


def test_returns_none_for_unknown_model():
    assert estimate_cost_usd("some-unlisted-model", 1000, 1000) is None


def test_returns_none_when_tokens_missing():
    assert estimate_cost_usd("gpt-4o-mini", None, 100) is None
    assert estimate_cost_usd("gpt-4o-mini", 100, None) is None


def test_computes_known_openai_pricing():
    # gpt-4o-mini: $0.15/1M input, $0.60/1M output
    cost = estimate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == 0.75


def test_computes_partial_million_proportionally():
    cost = estimate_cost_usd("gpt-4o-mini", 500_000, 0)
    assert cost == 0.075
