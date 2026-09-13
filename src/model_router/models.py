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


class ProviderUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
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


class CandidateMetrics(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
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
