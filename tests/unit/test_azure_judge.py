import pytest

from model_router.judging.azure_judge import AzureJudge, JudgeError
from model_router.models import ProviderResult, ProviderUsage, ResponsesRequest


class StubProvider:
    def __init__(self, output: str) -> None:
        self.output = output

    async def send(
        self,
        request: ResponsesRequest,
        upstream_model: str,
    ) -> ProviderResult:
        return ProviderResult(
            provider="azure",
            model=upstream_model,
            response={},
            output_text=self.output,
            usage=ProviderUsage(
                input_tokens=100,
                output_tokens=40,
                total_tokens=140,
            ),
            latency_ms=500,
        )

    async def list_models(self) -> list[str]:
        return []

    async def aclose(self) -> None:
        return None


def candidate(provider: str) -> ProviderResult:
    return ProviderResult(
        provider=provider,
        model="model",
        response={},
        output_text=f"{provider} answer",
        usage=ProviderUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        latency_ms=100,
    )


@pytest.mark.asyncio
async def test_judge_parses_and_maps_blinded_scores() -> None:
    provider = StubProvider(
        """
        {
          "candidate_a": {
            "correctness": 5, "relevance": 4, "completeness": 3,
            "rationale": "Good."
          },
          "candidate_b": {
            "correctness": 2, "relevance": 3, "completeness": 4,
            "rationale": "Mixed."
          }
        }
        """
    )
    result = await AzureJudge(provider=provider, deployment="judge").evaluate(
        prompt="test",
        candidates={"qwen": candidate("qwen"), "azure": candidate("azure")},
        evaluation_criteria="Be correct.",
    )

    assert set(result.assessments) == {"qwen", "azure"}
    assert sorted(item.score for item in result.assessments.values()) == [3, 4]
    assert result.usage is not None
    assert result.usage.total_tokens == 140


@pytest.mark.asyncio
async def test_judge_rejects_malformed_output() -> None:
    provider = StubProvider("not json")

    with pytest.raises(JudgeError, match="invalid structured output"):
        await AzureJudge(provider=provider, deployment="judge").evaluate(
            prompt="test",
            candidates={"qwen": candidate("qwen"), "azure": candidate("azure")},
            evaluation_criteria=None,
        )
