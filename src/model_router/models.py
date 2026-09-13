from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ResponsesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    input: str | list[dict[str, Any]]
    stream: bool = False
    instructions: str | None = None
    max_output_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = None
    chat_template_kwargs: dict[str, Any] | None = None


class ProviderUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    source: Literal["provider"] = "provider"


class ProviderResult(BaseModel):
    provider: str
    model: str
    response: dict[str, Any]
    output_text: str
    usage: ProviderUsage | None
    latency_ms: float = Field(ge=0)
    time_to_first_token_ms: float | None = Field(default=None, ge=0)
    decode_time_ms: float | None = Field(default=None, ge=0)
    finish_reason: str | None = None
    content_chunk_count: int = Field(default=0, ge=0)


class CandidateMetrics(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    reasoning_tokens: int | None
    latency_ms: float
    time_to_first_token_ms: float | None
    decode_time_ms: float | None
    output_input_ratio: float | None
    end_to_end_tokens_per_second: float | None
    decode_tokens_per_second: float | None
    tokens_per_successful_request: int | None
    estimated_cost_usd: float | None
    quality_score: float | None = None
    quality_per_1000_tokens: float | None = None


class ComparisonRequest(BaseModel):
    prompt: str = Field(min_length=1)
    instructions: str | None = None
    evaluation_criteria: str | None = None
    qwen_model: str | None = None
    azure_model: str | None = None
    max_output_tokens: int = Field(default=256, gt=0, le=4096)
    temperature: float = Field(default=0, ge=0, le=2)
    qwen_chat_template_kwargs: dict[str, Any] | None = None
    qwen_prompt_prefix: str | None = None

    @property
    def prompt_hash(self) -> str:
        return sha256(self.prompt.encode()).hexdigest()


class QualityAssessment(BaseModel):
    correctness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    rationale: str

    @property
    def score(self) -> float:
        return (self.correctness + self.relevance + self.completeness) / 3


class JudgeResult(BaseModel):
    assessments: dict[str, QualityAssessment]
    usage: ProviderUsage | None
    latency_ms: float = Field(ge=0)
    rubric: str


class CandidateOutcome(BaseModel):
    provider: str
    model: str
    result: ProviderResult | None = None
    metrics: CandidateMetrics | None = None
    error: str | None = None


class ComparisonResult(BaseModel):
    prompt_hash: str
    candidates: dict[str, CandidateOutcome]
    judge: JudgeResult | None = None
    judge_error: str | None = None
