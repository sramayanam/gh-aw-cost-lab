from dataclasses import dataclass

from model_router.config import Settings
from model_router.models import ProviderResult, ResponsesRequest
from model_router.providers.base import ResponsesProvider


class RoutingError(ValueError):
    pass


@dataclass(frozen=True)
class Route:
    provider: str
    upstream_model: str


def resolve_route(model: str, settings: Settings) -> Route:
    provider, separator, upstream_model = model.partition("/")
    if not separator or not upstream_model:
        raise RoutingError("Model must use qwen/<model> or azure/<deployment>")
    if provider == "qwen":
        return Route(provider="qwen", upstream_model=upstream_model)
    if provider == "azure":
        return Route(provider="azure", upstream_model=upstream_model)
    raise RoutingError(f"Unsupported model provider: {provider}")


class Router:
    def __init__(
        self,
        *,
        settings: Settings,
        qwen: ResponsesProvider,
        azure: ResponsesProvider,
    ) -> None:
        self._settings = settings
        self._providers = {"qwen": qwen, "azure": azure}

    async def route(self, request: ResponsesRequest) -> ProviderResult:
        route = resolve_route(request.model, self._settings)
        return await self._providers[route.provider].send(
            request,
            route.upstream_model,
        )
