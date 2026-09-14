#!/usr/bin/env python3
import argparse
import asyncio
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, TypedDict

import httpx

from model_router.comparison import ComparisonService
from model_router.config import Settings
from model_router.judging.azure_judge import AzureJudge
from model_router.models import ComparisonRequest, ComparisonResult
from model_router.providers.factory import create_azure_provider, create_qwen_provider

CASES = [
    {
        "id": "arithmetic",
        "prompt": (
            "A bat and a ball cost $1.10 total. The bat costs $1.00 more than "
            "the ball. State the ball's cost and briefly justify it."
        ),
        "criteria": "The ball costs $0.05 and the explanation is mathematically valid.",
    },
    {
        "id": "constraint-following",
        "prompt": (
            "Explain why leaves look green. Use exactly two sentences and no "
            "more than 35 words."
        ),
        "criteria": (
            "Exactly two sentences, at most 35 words, and correctly explains "
            "that chlorophyll reflects green wavelengths more than others."
        ),
    },
    {
        "id": "structured-extraction",
        "prompt": (
            "Return only JSON with keys name and quantity for this order: "
            "'Please ship 12 blue notebooks to Maya.'"
        ),
        "criteria": (
            'Valid JSON only, with name equal to "blue notebooks" and quantity '
            "equal to 12."
        ),
    },
    {
        "id": "code-reasoning",
        "prompt": (
            "What does this Python expression evaluate to, and why? "
            "[x * 2 for x in range(4) if x % 2 == 0]"
        ),
        "criteria": "The result is [0, 4] with a correct concise explanation.",
    },
    {
        "id": "factual",
        "prompt": (
            "In one paragraph, distinguish latency from throughput in an LLM "
            "inference service."
        ),
        "criteria": (
            "Correctly defines latency as time per request/token milestone and "
            "throughput as work or tokens completed per unit time."
        ),
    },
]


class BenchmarkProfile(TypedDict):
    description: str
    max_output_tokens: int
    temperature: float
    stop: str | list[str] | None
    instructions: str | None
    qwen_chat_template_kwargs: dict[str, Any] | None
    qwen_prompt_prefix: str | None


PROFILES: dict[str, BenchmarkProfile] = {
    "baseline": {
        "description": (
            "Identical zero-shot prompts and sampling settings for both providers."
        ),
        "max_output_tokens": 1000,
        "temperature": 0,
        "stop": None,
        "instructions": None,
        "qwen_chat_template_kwargs": None,
        "qwen_prompt_prefix": None,
    },
    "matched-concise": {
        "description": (
            "Identical concise system instruction, example, prompts, and sampling "
            "settings for both providers."
        ),
        "max_output_tokens": 256,
        "temperature": 0,
        "stop": None,
        "instructions": (
            "/no_think\n"
            "Return only the final answer; do not expose analysis or chain of "
            "thought. Follow every requested format and length constraint. Be "
            "concise and use no more than 80 output tokens unless the request "
            "requires more.\n"
            "Example request: What is 2 + 2? Return only the result.\n"
            "Example response: 4"
        ),
        "qwen_chat_template_kwargs": None,
        "qwen_prompt_prefix": None,
    },
    "qwen-no-thinking": {
        "description": (
            "Provider-optimized experiment; adds Qwen-only no-thinking controls, "
            "so prompts are intentionally not identical."
        ),
        "max_output_tokens": 256,
        "temperature": 0,
        "stop": None,
        "instructions": (
            "Return only the final answer; do not expose analysis or chain of "
            "thought. Follow every requested format and length constraint. Be "
            "concise and use no more than 80 output tokens unless the request "
            "requires more.\n"
            "Example request: What is 2 + 2? Return only the result.\n"
            "Example response: 4"
        ),
        "qwen_chat_template_kwargs": {"enable_thinking": False},
        "qwen_prompt_prefix": "/no_think\n",
    },
    "matched-stop": {
        "description": (
            "Identical prompts and sampling settings with an explicit final-answer "
            "delimiter and matched stop sequence for both providers."
        ),
        "max_output_tokens": 1000,
        "temperature": 0,
        "stop": "</final>",
        "instructions": (
            "Return only the concise final answer inside <final> and </final>. "
            "Do not expose analysis or chain of thought and do not write anything "
            "outside those tags.\n"
            "Example request: What is 2 + 2?\n"
            "Example response: <final>4</final>"
        ),
        "qwen_chat_template_kwargs": None,
        "qwen_prompt_prefix": None,
    },
}


async def run(profile_name: str) -> None:
    settings = Settings()
    judge_deployment = _configured_judge_deployment(settings)

    async with httpx.AsyncClient(
        timeout=settings.router_request_timeout_seconds
    ) as client:
        qwen = create_qwen_provider(settings, client)
        azure = create_azure_provider(settings, client)
        judge = AzureJudge(
            provider=azure,
            deployment=judge_deployment,
        )
        service = ComparisonService(
            settings=settings,
            qwen=qwen,
            azure=azure,
            judge=judge,
        )
        profile = PROFILES[profile_name]
        try:
            results = []
            for case in CASES:
                print(f"Running {case['id']}...", flush=True)
                results.append(
                    await service.compare(
                        ComparisonRequest(
                            prompt=case["prompt"],
                            instructions=profile["instructions"],
                            evaluation_criteria=case["criteria"],
                            max_output_tokens=profile["max_output_tokens"],
                            temperature=profile["temperature"],
                            stop=profile["stop"],
                            qwen_chat_template_kwargs=profile[
                                "qwen_chat_template_kwargs"
                            ],
                            qwen_prompt_prefix=profile["qwen_prompt_prefix"],
                        )
                    )
                )
        finally:
            await qwen.aclose()
            await azure.aclose()

    report = _report(
        results,
        profile_name,
        profile,
        judge_deployment=judge_deployment,
    )
    destination = settings.router_data_dir / f"benchmark-{profile_name}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    latest = settings.router_data_dir / "latest-benchmark.json"
    latest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _print_summary(report)
    print(f"\nMetric-only report: {destination}")


def _configured_judge_deployment(settings: Settings) -> str:
    deployment = (settings.azure_openai_judge_deployment or "").strip()
    if not deployment:
        raise RuntimeError(
            "Missing required configuration: AZURE_OPENAI_JUDGE_DEPLOYMENT"
        )
    return deployment


def _report(
    results: list[ComparisonResult],
    profile_name: str,
    profile: BenchmarkProfile,
    *,
    judge_deployment: str,
) -> dict[str, Any]:
    rows = []
    for case, result in zip(CASES, results, strict=True):
        row: dict[str, Any] = {"case": case["id"], "prompt_hash": result.prompt_hash}
        for provider, outcome in result.candidates.items():
            row[provider] = {
                "model": outcome.model,
                "error": outcome.error,
                "finish_reason": (
                    outcome.result.finish_reason if outcome.result is not None else None
                ),
                "metrics": (
                    outcome.metrics.model_dump(mode="json")
                    if outcome.metrics is not None
                    else None
                ),
            }
        row["judge"] = {
            "error": result.judge_error,
            "usage": (
                result.judge.usage.model_dump(mode="json")
                if result.judge is not None and result.judge.usage is not None
                else None
            ),
            "latency_ms": (
                result.judge.latency_ms if result.judge is not None else None
            ),
        }
        rows.append(row)
    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "profile": profile_name,
        "profile_description": profile["description"],
        "sampling": {
            "max_output_tokens": profile["max_output_tokens"],
            "temperature": profile["temperature"],
            "stop_sequences": profile["stop"],
            "shared_instructions": profile["instructions"] is not None,
            "qwen_chat_template_kwargs": profile["qwen_chat_template_kwargs"],
            "prompts_identical": profile["qwen_prompt_prefix"] is None,
            "qwen_prompt_prefix": profile["qwen_prompt_prefix"],
            "judge_deployment": judge_deployment,
        },
        "aggregate": _aggregate(results),
        "cases": rows,
    }


def _aggregate(results: list[ComparisonResult]) -> dict[str, Any]:
    aggregate: dict[str, Any] = {}
    for provider in ("qwen", "azure"):
        metrics = [
            result.candidates[provider].metrics
            for result in results
            if result.candidates[provider].metrics is not None
        ]
        aggregate[provider] = {
            "successful_cases": len(metrics),
            "length_limited_cases": sum(
                _is_length_limited(result, provider) for result in results
            ),
            "total_candidate_tokens": sum(
                item.total_tokens or 0 for item in metrics if item is not None
            ),
            "total_input_tokens": sum(
                item.input_tokens or 0 for item in metrics if item is not None
            ),
            "total_output_tokens": sum(
                item.output_tokens or 0 for item in metrics if item is not None
            ),
            "total_output_characters": sum(
                item.output_characters for item in metrics if item is not None
            ),
            "total_output_words": sum(
                item.output_words for item in metrics if item is not None
            ),
            "average_quality_score": _average(
                item.quality_score for item in metrics if item is not None
            ),
            "average_latency_ms": _average(
                item.latency_ms for item in metrics if item is not None
            ),
            "average_ttft_ms": _average(
                item.time_to_first_token_ms for item in metrics if item is not None
            ),
            "average_decode_tokens_per_second": _average(
                item.decode_tokens_per_second for item in metrics if item is not None
            ),
            "average_quality_per_1000_tokens": _average(
                item.quality_per_1000_tokens for item in metrics if item is not None
            ),
        }
    judge_usage = [
        result.judge.usage
        for result in results
        if result.judge is not None and result.judge.usage is not None
    ]
    aggregate["judge"] = {
        "successful_cases": len(judge_usage),
        "total_tokens": sum(item.total_tokens for item in judge_usage),
        "average_latency_ms": _average(
            result.judge.latency_ms for result in results if result.judge is not None
        ),
    }
    return aggregate


def _is_length_limited(result: ComparisonResult, provider: str) -> bool:
    provider_result = result.candidates[provider].result
    return provider_result is not None and provider_result.finish_reason == "length"


def _average(values: Iterable[float | int | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def _print_summary(report: dict[str, Any]) -> None:
    print(
        "\ncase                    provider  score  tokens  latency_ms  "
        "ttft_ms  decode_tok_s"
    )
    print("-" * 86)
    for row in report["cases"]:
        for provider in ("qwen", "azure"):
            candidate = row[provider]
            metrics = candidate["metrics"]
            if metrics is None:
                print(f"{row['case']:<23} {provider:<9} ERROR: {candidate['error']}")
                continue
            print(
                f"{row['case']:<23} {provider:<9} "
                f"{_number(metrics['quality_score']):>5} "
                f"{_number(metrics['total_tokens']):>7} "
                f"{_number(metrics['latency_ms']):>11} "
                f"{_number(metrics['time_to_first_token_ms']):>8} "
                f"{_number(metrics['decode_tokens_per_second']):>12}"
            )
    print("\nAggregate")
    for provider in ("qwen", "azure"):
        metrics = report["aggregate"][provider]
        print(
            f"{provider}: quality={_number(metrics['average_quality_score'])}, "
            f"tokens={metrics['total_candidate_tokens']}, "
            f"chars={metrics['total_output_characters']}, "
            f"words={metrics['total_output_words']}, "
            f"length_limited={metrics['length_limited_cases']}, "
            f"latency_ms={_number(metrics['average_latency_ms'])}, "
            f"ttft_ms={_number(metrics['average_ttft_ms'])}, "
            "decode_tok_s="
            f"{_number(metrics['average_decode_tokens_per_second'])}, "
            "quality_per_1k="
            f"{_number(metrics['average_quality_per_1000_tokens'])}"
        )
    judge = report["aggregate"]["judge"]
    print(
        f"judge: tokens={judge['total_tokens']}, "
        f"average_latency_ms={_number(judge['average_latency_ms'])}"
    )


def _number(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="baseline",
    )
    arguments = parser.parse_args()
    asyncio.run(run(arguments.profile))
