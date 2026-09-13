import json

import httpx
import pytest

from model_router.models import ResponsesRequest
from model_router.providers.base import ProviderError
from model_router.providers.openai_chat_completions import (
    OpenAIChatCompletionsProvider,
)


@pytest.mark.asyncio
async def test_provider_normalizes_usage_and_output_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test"
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert payload["stream_options"] == {"include_usage": True}
        return httpx.Response(
            200,
            text=(
                'data: {"id":"chat_1","choices":[{"delta":{"content":"hel"}}]}\n\n'
                'data: {"id":"chat_1","choices":[{"delta":{"content":"lo"}}]}\n\n'
                'data: {"choices":[],"usage":{"prompt_tokens":4,'
                '"completion_tokens":2,"total_tokens":6}}\n\n'
                "data: [DONE]\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIChatCompletionsProvider(
            name="qwen",
            chat_completions_url=lambda _model: "http://qwen.test/v1/chat/completions",
            models_url="http://qwen.test/v1/models",
            headers={"Authorization": "Bearer test"},
            client=client,
        )
        result = await provider.send(
            ResponsesRequest(model="qwen/test", input="hi"),
            "test",
        )

    assert result.output_text == "hello"
    assert result.usage is not None
    assert result.usage.total_tokens == 6
    assert result.time_to_first_token_ms is not None
    assert result.decode_time_ms is not None
    assert result.response["output_text"] == "hello"


@pytest.mark.asyncio
async def test_provider_rejects_client_streaming() -> None:
    async with httpx.AsyncClient() as client:
        provider = OpenAIChatCompletionsProvider(
            name="qwen",
            chat_completions_url=lambda _model: "http://qwen.test/v1/chat/completions",
            models_url=None,
            headers={},
            client=client,
        )
        with pytest.raises(ProviderError, match="streaming"):
            await provider.send(
                ResponsesRequest(model="qwen/test", input="hi", stream=True),
                "test",
            )


@pytest.mark.asyncio
async def test_provider_surfaces_status_without_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"code": "invalid_api_key", "message": "secret text"}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIChatCompletionsProvider(
            name="azure",
            chat_completions_url=lambda _model: (
                "https://azure.test/openai/deployments/test/chat/completions"
            ),
            models_url=None,
            headers={},
            client=client,
        )
        with pytest.raises(ProviderError) as error:
            await provider.send(
                ResponsesRequest(model="azure/test", input="hi"),
                "test",
            )

    assert error.value.status_code == 401
    assert "secret text" not in str(error.value)


@pytest.mark.asyncio
async def test_provider_leaves_usage_missing_when_final_chunk_has_no_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n'
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIChatCompletionsProvider(
            name="qwen",
            chat_completions_url=lambda _model: "http://qwen.test/v1/chat/completions",
            models_url=None,
            headers={},
            client=client,
        )
        result = await provider.send(
            ResponsesRequest(model="qwen/test", input="hi"),
            "test",
        )

    assert result.output_text == "hello"
    assert result.usage is None


@pytest.mark.asyncio
async def test_provider_lists_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json={"data": [{"id": "qwen3.5-2b-text"}, {"invalid": "ignored"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIChatCompletionsProvider(
            name="qwen",
            chat_completions_url=lambda _model: "http://qwen.test/v1/chat/completions",
            models_url="http://qwen.test/v1/models",
            headers={},
            client=client,
        )

        assert await provider.list_models() == ["qwen3.5-2b-text"]


@pytest.mark.asyncio
async def test_provider_surfaces_transport_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIChatCompletionsProvider(
            name="qwen",
            chat_completions_url=lambda _model: "http://qwen.test/v1/chat/completions",
            models_url=None,
            headers={},
            client=client,
        )

        with pytest.raises(ProviderError, match="qwen request failed"):
            await provider.send(
                ResponsesRequest(model="qwen/test", input="hi"),
                "test",
            )


@pytest.mark.asyncio
async def test_provider_uses_dynamic_bearer_token() -> None:
    async def token_provider() -> str:
        return "entra-token"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer entra-token"
        return httpx.Response(200, text="data: [DONE]\n\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIChatCompletionsProvider(
            name="azure",
            chat_completions_url=lambda _model: (
                "https://azure.test/openai/v1/chat/completions"
            ),
            models_url=None,
            headers={},
            client=client,
            bearer_token_provider=token_provider,
        )

        await provider.send(
            ResponsesRequest(model="azure/gpt-4.1-mini", input="hi"),
            "gpt-4.1-mini",
        )
