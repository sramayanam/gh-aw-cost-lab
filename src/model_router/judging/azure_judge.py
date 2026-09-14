import json
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ValidationError

from model_router.models import (
    JudgeResult,
    ProviderResult,
    QualityAssessment,
    ResponsesRequest,
)
from model_router.providers.base import ResponsesProvider

RUBRIC = (
    "Score each dimension from 1 (poor) to 5 (excellent). Correctness measures "
    "factual and logical accuracy. Relevance measures directness and adherence "
    "to the request. Completeness measures whether all requested elements are "
    "present. Evaluate only the supplied text and criteria."
)


class JudgeError(RuntimeError):
    pass


class _JudgePayload(BaseModel):
    candidate_a: QualityAssessment
    candidate_b: QualityAssessment


class AzureJudge:
    def __init__(
        self,
        *,
        provider: ResponsesProvider,
        deployment: str,
    ) -> None:
        self._provider = provider
        self._deployment = deployment

    async def evaluate(
        self,
        *,
        prompt: str,
        candidates: dict[str, ProviderResult],
        evaluation_criteria: str | None,
    ) -> JudgeResult:
        if len(candidates) != 2:
            raise JudgeError("Quality judging requires two successful candidates")

        ordered = _blind_order(prompt, candidates)
        labels = ("candidate_a", "candidate_b")
        labeled = dict(zip(labels, ordered, strict=True))
        judge_input = {
            "original_request": prompt,
            "evaluation_criteria": evaluation_criteria
            or "Answer the original request accurately and completely.",
            "candidate_a": candidates[labeled["candidate_a"]].output_text,
            "candidate_b": candidates[labeled["candidate_b"]].output_text,
        }
        result = await self._provider.send(
            ResponsesRequest(
                model=f"azure/{self._deployment}",
                instructions=(
                    "You are an impartial response evaluator. "
                    f"{RUBRIC} Return only one JSON object with keys candidate_a "
                    "and candidate_b. Each value must contain integer fields "
                    "correctness, relevance, completeness and a brief rationale."
                ),
                input=json.dumps(judge_input, ensure_ascii=True),
                max_output_tokens=512,
                temperature=0,
            ),
            self._deployment,
        )
        payload = _parse_payload(result.output_text)
        by_provider = {
            provider: getattr(payload, label) for label, provider in labeled.items()
        }
        return JudgeResult(
            assessments=by_provider,
            usage=result.usage,
            latency_ms=result.latency_ms,
            rubric=RUBRIC,
        )


def _blind_order(prompt: str, candidates: dict[str, ProviderResult]) -> list[str]:
    providers = sorted(candidates)
    if sha256(prompt.encode()).digest()[0] % 2:
        providers.reverse()
    return providers


def _parse_payload(output: str) -> _JudgePayload:
    value = output.strip()
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1])
    try:
        data: Any = json.loads(value)
        return _JudgePayload.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise JudgeError("Azure judge returned invalid structured output") from exc
