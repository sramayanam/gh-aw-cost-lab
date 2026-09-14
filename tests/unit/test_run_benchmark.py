import importlib.util
import json
from pathlib import Path

import pytest

from model_router.config import Settings
from model_router.models import (
    CandidateMetrics,
    CandidateOutcome,
    ComparisonResult,
    JudgeResult,
    ProviderResult,
    ProviderUsage,
    QualityAssessment,
    ResponsesRequest,
)


class FakeProvider:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.upstream_models: list[str] = []

    async def send(
        self,
        request: ResponsesRequest,
        upstream_model: str,
    ) -> ProviderResult:
        self.upstream_models.append(upstream_model)
        output_text = f"{self.provider} answer"
        if request.model == "azure/gpt-5.4":
            output_text = """
            {
              "candidate_a": {
                "correctness": 4,
                "relevance": 4,
                "completeness": 4,
                "rationale": "Good."
              },
              "candidate_b": {
                "correctness": 5,
                "relevance": 5,
                "completeness": 5,
                "rationale": "Great."
              }
            }
            """
        return ProviderResult(
            provider=self.provider,
            model=upstream_model,
            response={},
            output_text=output_text,
            usage=ProviderUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            latency_ms=100,
            time_to_first_token_ms=20,
            decode_time_ms=50,
        )

    async def list_models(self) -> list[str]:
        return []

    async def aclose(self) -> None:
        return None


_RUN_BENCHMARK_PATH = Path(__file__).parents[2] / "scripts" / "run_benchmark.py"
_SPEC = importlib.util.spec_from_file_location("run_benchmark", _RUN_BENCHMARK_PATH)
assert _SPEC is not None
run_benchmark = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(run_benchmark)


def test_benchmark_report_records_judge_deployment() -> None:
    report = run_benchmark._report(
        [_result() for _ in run_benchmark.CASES],
        "baseline",
        run_benchmark.PROFILES["baseline"],
        judge_deployment="gpt-5.4",
    )

    assert report["sampling"]["judge_deployment"] == "gpt-5.4"


def test_configured_judge_deployment_strips_whitespace() -> None:
    settings = Settings(
        _env_file=None,
        AZURE_OPENAI_JUDGE_DEPLOYMENT=" gpt-5.4 ",
    )

    assert run_benchmark._configured_judge_deployment(settings) == "gpt-5.4"


def test_configured_judge_deployment_rejects_blank_value() -> None:
    settings = Settings(_env_file=None, AZURE_OPENAI_JUDGE_DEPLOYMENT=" ")

    with pytest.raises(
        RuntimeError,
        match="Missing required configuration: AZURE_OPENAI_JUDGE_DEPLOYMENT",
    ):
        run_benchmark._configured_judge_deployment(settings)


@pytest.mark.asyncio
async def test_run_uses_configured_judge_deployment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qwen = FakeProvider("qwen")
    azure = FakeProvider("azure")
    settings = Settings(
        _env_file=None,
        AZURE_OPENAI_DEPLOYMENT="gpt-4.1-mini",
        AZURE_OPENAI_JUDGE_DEPLOYMENT=" gpt-5.4 ",
        ROUTER_DATA_DIR=tmp_path,
    )
    monkeypatch.setattr(run_benchmark, "Settings", lambda: settings)
    monkeypatch.setattr(run_benchmark, "create_qwen_provider", lambda *_: qwen)
    monkeypatch.setattr(run_benchmark, "create_azure_provider", lambda *_: azure)

    await run_benchmark.run("baseline")

    report = json.loads((tmp_path / "benchmark-baseline.json").read_text())
    assert "gpt-5.4" in azure.upstream_models
    assert report["sampling"]["judge_deployment"] == "gpt-5.4"


def _result() -> ComparisonResult:
    return ComparisonResult(
        prompt_hash="hash",
        candidates={
            "qwen": _outcome("qwen"),
            "azure": _outcome("azure"),
        },
        judge=JudgeResult(
            assessments={
                "qwen": QualityAssessment(
                    correctness=4,
                    relevance=4,
                    completeness=4,
                    rationale="Good.",
                ),
                "azure": QualityAssessment(
                    correctness=5,
                    relevance=5,
                    completeness=5,
                    rationale="Great.",
                ),
            },
            usage=ProviderUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            latency_ms=100,
            rubric="rubric",
        ),
    )


def _outcome(provider: str) -> CandidateOutcome:
    return CandidateOutcome(
        provider=provider,
        model="model",
        metrics=CandidateMetrics(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            reasoning_tokens=None,
            output_characters=20,
            output_words=4,
            characters_per_output_token=4,
            latency_ms=100,
            time_to_first_token_ms=20,
            decode_time_ms=50,
            output_input_ratio=0.5,
            end_to_end_tokens_per_second=50,
            decode_tokens_per_second=100,
            tokens_per_successful_request=15,
            estimated_cost_usd=0,
            quality_score=4,
            quality_per_1000_tokens=266.67,
        ),
    )
