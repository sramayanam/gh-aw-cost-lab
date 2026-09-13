import json
from collections.abc import Awaitable, Callable, Mapping
from time import perf_counter
from typing import Any

import httpx

from model_router.models import ProviderResult, ProviderUsage, ResponsesRequest
from model_router.providers.base import ProviderError


class OpenAIChatCompletionsProvider:
    def __init__(
        self,
        *,
        name: str,
        chat_completions_url: Callable[[str], str],
        models_url: str | None,
        headers: Mapping[str, str],
        client: httpx.AsyncClient,
        bearer_token_provider: Callable[[], Awaitable[str]] | None = None,
        close_callback: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.name = name
        self._chat_completions_url = chat_completions_url
        self._models_url = models_url
        self._headers = dict(headers)
        self._client = client
        self._bearer_token_provider = bearer_token_provider
        self._close_callback = close_callback

    async def send(
        self,
        request: ResponsesRequest,
        upstream_model: str,
    ) -> ProviderResult:
        if request.stream:
            raise ProviderError(
                self.name, "Client-facing streaming is not supported in v1"
            )

        payload = _chat_payload(request, upstream_model, self.name)
        started = perf_counter()
        first_token_at: float | None = None
        chunks: list[str] = []
        usage: ProviderUsage | None = None
        response_id: str | None = None
        finish_reason: str | None = None
        try:
            async with self._client.stream(
                "POST",
                self._chat_completions_url(upstream_model),
                headers=await self._request_headers(),
                json=payload,
            ) as response:
                if not response.is_success:
                    await response.aread()
                    raise ProviderError(
                        self.name,
                        _provider_error_message(response),
                        response.status_code,
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    chunk = _parse_stream_chunk(data, self.name)
                    chunk_id = chunk.get("id")
                    if isinstance(chunk_id, str):
                        response_id = chunk_id
                    usage = _extract_usage(chunk) or usage
                    finish_reason = _extract_finish_reason(chunk) or finish_reason
                    delta = _extract_delta(chunk)
                    if delta:
                        if first_token_at is None:
                            first_token_at = perf_counter()
                        chunks.append(delta)
        except httpx.HTTPError as exc:
            raise ProviderError(self.name, f"{self.name} request failed") from exc
        finished = perf_counter()
        output_text = "".join(chunks)
        body = _responses_body(
            response_id=response_id,
            model=upstream_model,
            output_text=output_text,
            usage=usage,
        )

        return ProviderResult(
            provider=self.name,
            model=upstream_model,
            response=body,
            output_text=output_text,
            usage=usage,
            latency_ms=(finished - started) * 1000,
            time_to_first_token_ms=(
                (first_token_at - started) * 1000
                if first_token_at is not None
                else None
            ),
            decode_time_ms=(
                (finished - first_token_at) * 1000
                if first_token_at is not None
                else None
            ),
            finish_reason=finish_reason,
        )

    async def list_models(self) -> list[str]:
        if self._models_url is None:
            return []
        try:
            response = await self._client.get(
                self._models_url,
                headers=await self._request_headers(),
            )
        except httpx.HTTPError as exc:
            raise ProviderError(
                self.name, f"{self.name} model discovery failed"
            ) from exc
        if not response.is_success:
            raise ProviderError(
                self.name,
                _provider_error_message(response),
                response.status_code,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderError(
                self.name, f"{self.name} returned invalid JSON"
            ) from exc
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            raise ProviderError(self.name, f"{self.name} returned invalid model data")
        return [
            item["id"]
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]

    async def aclose(self) -> None:
        if self._close_callback is not None:
            await self._close_callback()

    async def _request_headers(self) -> dict[str, str]:
        headers = dict(self._headers)
        if self._bearer_token_provider is not None:
            token = await self._bearer_token_provider()
            headers["Authorization"] = f"Bearer {token}"
        return headers


def _chat_payload(
    request: ResponsesRequest,
    upstream_model: str,
    provider: str,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if request.instructions:
        messages.append({"role": "system", "content": request.instructions})
    if isinstance(request.input, str):
        messages.append({"role": "user", "content": request.input})
    else:
        for item in request.input:
            role = item.get("role")
            content = item.get("content")
            if not isinstance(role, str) or not isinstance(content, str):
                raise ProviderError(
                    provider,
                    "Only string message content is supported in version 1",
                )
            messages.append({"role": role, "content": content})

    payload: dict[str, Any] = {
        "model": upstream_model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if request.max_output_tokens is not None:
        payload["max_tokens"] = request.max_output_tokens
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    return payload


def _parse_stream_chunk(data: str, provider: str) -> dict[str, Any]:
    try:
        chunk = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ProviderError(
            provider, f"{provider} returned invalid stream JSON"
        ) from exc
    if not isinstance(chunk, dict):
        raise ProviderError(provider, f"{provider} returned invalid stream data")
    return chunk


def _extract_delta(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0]
    if not isinstance(choice, dict):
        return ""
    delta = choice.get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


def _extract_finish_reason(chunk: dict[str, Any]) -> str | None:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    choice = choices[0]
    if not isinstance(choice, dict):
        return None
    finish_reason = choice.get("finish_reason")
    return finish_reason if isinstance(finish_reason, str) else None


def _extract_usage(body: dict[str, Any]) -> ProviderUsage | None:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    if not isinstance(total_tokens, int):
        total_tokens = input_tokens + output_tokens
    return ProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _responses_body(
    *,
    response_id: str | None,
    model: str,
    output_text: str,
    usage: ProviderUsage | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": response_id,
        "object": "response",
        "model": model,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": output_text}],
            }
        ],
        "output_text": output_text,
    }
    if usage is not None:
        body["usage"] = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        }
    return body


def _provider_error_message(response: httpx.Response) -> str:
    prefix = f"Provider request failed with status {response.status_code}"
    try:
        body = response.json()
    except ValueError:
        return prefix
    if not isinstance(body, dict):
        return prefix
    error = body.get("error")
    if not isinstance(error, dict):
        return prefix
    code = error.get("code")
    if isinstance(code, str) and code:
        return f"{prefix} ({code[:80]})"
    return prefix
