from model_router.providers.factory import (
    _azure_chat_completions_url,
    _chat_completions_url,
    _models_url,
)


def test_foundry_local_urls() -> None:
    base_url = "http://127.0.0.1:49508/v1"

    assert _chat_completions_url(base_url) == (
        "http://127.0.0.1:49508/v1/chat/completions"
    )
    assert _models_url(base_url) == "http://127.0.0.1:49508/v1/models"


def test_azure_v1_chat_completions_url() -> None:
    endpoint = "https://example.openai.azure.com/openai/v1"

    assert _azure_chat_completions_url(endpoint) == (
        "https://example.openai.azure.com/openai/v1/chat/completions"
    )
