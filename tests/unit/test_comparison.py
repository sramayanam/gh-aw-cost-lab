import pytest

from model_router.comparison import ComparisonService
from model_router.config import Settings
from model_router.models import (
    ComparisonRequest,
    JudgeResult,
    ProviderResult,
    ProviderUsage,
    QualityAssessment,
    ResponsesRequest,
)
from model_router.providers.base import ProviderError


class StubProvider:
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self.fail = fail

    async def send(
        self,
        request: ResponsesRequest,
        upstream_model: str,
    ) -> ProviderResult:
        if self.fail:
            raise ProviderError(self.name, f"{self.name} failed")
        return ProviderResult(
            provider=self.name,
            model=upstream_model,
            response={},
            output_text=f"{self.name} answer",
            usage=ProviderUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            latency_ms=100,
            time_to_first_token_ms=20,
            decode_time_ms=50,
        )

    async def list_models(self) -> list[str]:
        return []

    async def aclose(self) -> None:
        return None


class StubJudge:
    async def evaluate(
        self,
        *,
        prompt: str,
        candidates: dict[str, ProviderResult],
        evaluation_criteria: str | None,
    ) -> JudgeResult:
        return JudgeResult(
            assessments={
                name: QualityAssessment(
                    correctness=4,
                    relevance=5,
                    completeness=3,
                    rationale="Good.",
                )
                for name in candidates
            },
            usage=ProviderUsage(
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
            ),
            latency_ms=200,
            rubric="rubric",
        )


@pytest.mark.asyncio
async def test_comparison_scores_both_candidates() -> None:
    service = ComparisonService(
        settings=Settings(_env_file=None, AZURE_OPENAI_DEPLOYMENT="azure-model"),
        qwen=StubProvider("qwen"),
        azure=StubProvider("azure"),
        judge=StubJudge(),
    )

    result = await service.compare(ComparisonRequest(prompt="test"))

    assert result.judge is not None
    assert result.judge_error is None
    assert result.candidates["qwen"].metrics is not None
    assert result.candidates["qwen"].metrics.quality_score == 4
    assert result.candidates["azure"].metrics is not None
    assert result.candidates["azure"].metrics.quality_score == 4


@pytest.mark.asyncio
async def test_comparison_preserves_partial_provider_failure() -> None:
    service = ComparisonService(
        settings=Settings(_env_file=None, AZURE_OPENAI_DEPLOYMENT="azure-model"),
        qwen=StubProvider("qwen", fail=True),
        azure=StubProvider("azure"),
        judge=StubJudge(),
    )

    result = await service.compare(ComparisonRequest(prompt="test"))

    assert result.candidates["qwen"].error == "qwen failed"
    assert result.candidates["azure"].result is not None
    assert result.judge is None
    assert result.judge_error == "Quality judging requires two successful candidates"
