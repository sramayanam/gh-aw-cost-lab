from model_router.models import CandidateMetrics, ProviderResult


def candidate_metrics(
    result: ProviderResult,
    *,
    input_cost_per_million: float | None = None,
    output_cost_per_million: float | None = None,
    hourly_cost_usd: float | None = None,
    quality_score: float | None = None,
) -> CandidateMetrics:
    usage = result.usage
    latency_seconds = result.latency_ms / 1000
    input_tokens = usage.input_tokens if usage else None
    output_tokens = usage.output_tokens if usage else None
    total_tokens = usage.total_tokens if usage else None

    output_input_ratio = None
    if input_tokens is not None and input_tokens != 0 and output_tokens is not None:
        output_input_ratio = output_tokens / input_tokens

    end_to_end_tokens_per_second = None
    if output_tokens is not None and latency_seconds > 0:
        end_to_end_tokens_per_second = output_tokens / latency_seconds

    decode_tokens_per_second = None
    if (
        output_tokens is not None
        and result.decode_time_ms is not None
        and result.decode_time_ms > 0
    ):
        decode_tokens_per_second = output_tokens / (result.decode_time_ms / 1000)

    estimated_cost = _estimated_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_seconds=latency_seconds,
        input_cost_per_million=input_cost_per_million,
        output_cost_per_million=output_cost_per_million,
        hourly_cost_usd=hourly_cost_usd,
    )
    quality_per_1000_tokens = None
    if quality_score is not None and total_tokens is not None and total_tokens != 0:
        quality_per_1000_tokens = quality_score * 1000 / total_tokens

    return CandidateMetrics(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        latency_ms=result.latency_ms,
        time_to_first_token_ms=result.time_to_first_token_ms,
        decode_time_ms=result.decode_time_ms,
        output_input_ratio=output_input_ratio,
        end_to_end_tokens_per_second=end_to_end_tokens_per_second,
        decode_tokens_per_second=decode_tokens_per_second,
        tokens_per_successful_request=total_tokens,
        estimated_cost_usd=estimated_cost,
        quality_score=quality_score,
        quality_per_1000_tokens=quality_per_1000_tokens,
    )


def _estimated_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    latency_seconds: float,
    input_cost_per_million: float | None,
    output_cost_per_million: float | None,
    hourly_cost_usd: float | None,
) -> float | None:
    if hourly_cost_usd is not None:
        return hourly_cost_usd * latency_seconds / 3600
    if (
        input_tokens is None
        or output_tokens is None
        or input_cost_per_million is None
        or output_cost_per_million is None
    ):
        return None
    return (
        input_tokens * input_cost_per_million + output_tokens * output_cost_per_million
    ) / 1_000_000
