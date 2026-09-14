from typing import Protocol

from model_router.models import ProviderResult, ResponsesRequest


class ProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class ResponsesProvider(Protocol):
    name: str

    async def send(
        self,
        request: ResponsesRequest,
        upstream_model: str,
    ) -> ProviderResult: ...

    async def list_models(self) -> list[str]: ...

    async def aclose(self) -> None: ...
