from collections.abc import Callable

import httpx
from azure.identity.aio import DefaultAzureCredential

from model_router.config import Settings
from model_router.providers.openai_chat_completions import (
    OpenAIChatCompletionsProvider,
)

AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"


class ConfigurationError(RuntimeError):
    pass


def create_qwen_provider(
    settings: Settings,
    client: httpx.AsyncClient,
) -> OpenAIChatCompletionsProvider:
    if settings.qwen_base_url is None:
        raise ConfigurationError("Missing required configuration: QWEN_BASE_URL")
    headers = {"Content-Type": "application/json"}
    if settings.qwen_api_key is not None:
        headers["Authorization"] = f"Bearer {settings.qwen_api_key.get_secret_value()}"
    return OpenAIChatCompletionsProvider(
        name="qwen",
        chat_completions_url=_fixed_url(_chat_completions_url(settings.qwen_base_url)),
        models_url=_models_url(settings.qwen_base_url),
        headers=headers,
        client=client,
    )


def create_azure_provider(
    settings: Settings,
    client: httpx.AsyncClient,
) -> OpenAIChatCompletionsProvider:
    missing = [
        name
        for name, value in (
            ("AZURE_OPENAI_ENDPOINT", settings.azure_openai_endpoint),
            ("AZURE_OPENAI_DEPLOYMENT", settings.azure_openai_deployment),
        )
        if value is None
    ]
    if missing:
        raise ConfigurationError(
            f"Missing required configuration: {', '.join(missing)}"
        )
    assert settings.azure_openai_endpoint is not None

    headers = {"Content-Type": "application/json"}
    bearer_token_provider = None
    close_callback = None
    if settings.azure_openai_api_key is not None:
        headers["api-key"] = settings.azure_openai_api_key.get_secret_value()
    else:
        credential = DefaultAzureCredential()

        async def get_token() -> str:
            token = await credential.get_token(AZURE_OPENAI_SCOPE)
            return token.token

        bearer_token_provider = get_token
        close_callback = credential.close

    return OpenAIChatCompletionsProvider(
        name="azure",
        chat_completions_url=_fixed_url(
            _azure_chat_completions_url(settings.azure_openai_endpoint)
        ),
        models_url=None,
        headers=headers,
        client=client,
        bearer_token_provider=bearer_token_provider,
        close_callback=close_callback,
    )


def _fixed_url(url: str) -> Callable[[str], str]:
    return lambda _model: url


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _models_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        normalized = normalized.removesuffix("/chat/completions")
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return f"{normalized}/models"


def _azure_chat_completions_url(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/openai/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/openai/v1/chat/completions"
