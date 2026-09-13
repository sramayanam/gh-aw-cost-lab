import asyncio
from typing import Protocol

from model_router.config import Settings
from model_router.metrics import candidate_metrics
from model_router.models import (
    CandidateOutcome,
    ComparisonRequest,
    ComparisonResult,
    JudgeResult,
    ProviderResult,
    ResponsesRequest,
)
from model_router.providers.base import ProviderError, ResponsesProvider


class QualityJudge(Protocol):
    async def evaluate(
        self,
        *,
        prompt: str,
        candidates: dict[str, ProviderResult],
        evaluation_criteria: str | None,
    ) -> JudgeResult: ...


class ComparisonService:
    def __init__(
        self,
        *,
        settings: Settings,
        qwen: ResponsesProvider,
        azure: ResponsesProvider,
        judge: QualityJudge,
    ) -> None:
        self._settings = settings
        self._qwen = qwen
        self._azure = azure
        self._judge = judge

    async def compare(self, request: ComparisonRequest) -> ComparisonResult:
        qwen_model = request.qwen_model or self._settings.qwen_model
        azure_model = request.azure_model or self._settings.azure_openai_deployment
        if azure_model is None:
            raise ValueError("Missing required configuration: AZURE_OPENAI_DEPLOYMENT")

        qwen, azure = await asyncio.gather(
            self._run_candidate("qwen", qwen_model, self._qwen, request),
            self._run_candidate("azure", azure_model, self._azure, request),
        )
        outcomes = {"qwen": qwen, "azure": azure}
        successful = {
            name: outcome.result
            for name, outcome in outcomes.items()
            if outcome.result is not None
        }
        judge_result = None
        judge_error = None
        if len(successful) == 2:
            try:
                judge_result = await self._judge.evaluate(
                    prompt=request.prompt,
                    candidates={
                        name: result
                        for name, result in successful.items()
                        if result is not None
                    },
                    evaluation_criteria=request.evaluation_criteria,
                )
            except ProviderError as exc:
                judge_error = str(exc)
            except RuntimeError as exc:
                judge_error = str(exc)
        else:
            judge_error = "Quality judging requires two successful candidates"

        for name, outcome in outcomes.items():
            if outcome.result is None:
                continue
            score = None
            if judge_result is not None:
                assessment = judge_result.assessments.get(name)
                score = assessment.score if assessment is not None else None
            if name == "qwen":
                outcome.metrics = candidate_metrics(
                    outcome.result,
                    hourly_cost_usd=self._settings.qwen_hourly_cost_usd,
                    quality_score=score,
                )
            else:
                outcome.metrics = candidate_metrics(
                    outcome.result,
                    input_cost_per_million=(
                        self._settings.azure_input_cost_per_million
                    ),
                    output_cost_per_million=(
                        self._settings.azure_output_cost_per_million
                    ),
                    quality_score=score,
                )

        return ComparisonResult(
            prompt_hash=request.prompt_hash,
            candidates=outcomes,
            judge=judge_result,
            judge_error=judge_error,
        )

    async def _run_candidate(
        self,
        name: str,
        model: str,
        provider: ResponsesProvider,
        request: ComparisonRequest,
    ) -> CandidateOutcome:
        try:
            result = await provider.send(
                ResponsesRequest(
                    model=f"{name}/{model}",
                    input=(
                        f"{request.qwen_prompt_prefix}{request.prompt}"
                        if name == "qwen" and request.qwen_prompt_prefix
                        else request.prompt
                    ),
                    instructions=request.instructions,
                    max_output_tokens=request.max_output_tokens,
                    temperature=request.temperature,
                    stop=request.stop,
                    chat_template_kwargs=(
                        request.qwen_chat_template_kwargs if name == "qwen" else None
                    ),
                ),
                model,
            )
        except ProviderError as exc:
            return CandidateOutcome(
                provider=name,
                model=model,
                error=str(exc),
            )
        return CandidateOutcome(
            provider=name,
            model=model,
            result=result,
        )
