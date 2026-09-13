import pytest

from model_router.metrics import candidate_metrics
from model_router.models import ProviderResult, ProviderUsage


def result() -> ProviderResult:
    return ProviderResult(
        provider="azure",
        model="deployment",
        response={},
        output_text="answer",
        usage=ProviderUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        latency_ms=2000,
        time_to_first_token_ms=500,
        decode_time_ms=1000,
    )


def test_commercial_metrics() -> None:
    metrics = candidate_metrics(
        result(),
        input_cost_per_million=2,
        output_cost_per_million=8,
        quality_score=4,
    )

    assert metrics.output_input_ratio == 0.5
    assert metrics.end_to_end_tokens_per_second == 25
    assert metrics.decode_tokens_per_second == 50
    assert metrics.time_to_first_token_ms == 500
    assert metrics.estimated_cost_usd == pytest.approx(0.0006)
    assert metrics.quality_per_1000_tokens == pytest.approx(26.6666667)


def test_managed_hosting_cost_uses_request_duration() -> None:
    metrics = candidate_metrics(result(), hourly_cost_usd=3.6)

    assert metrics.estimated_cost_usd == pytest.approx(0.002)
