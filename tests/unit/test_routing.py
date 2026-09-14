from model_router.config import Settings
from model_router.routing import RoutingError, resolve_route


def test_resolve_qwen_route() -> None:
    route = resolve_route("qwen/qwen2.5", Settings())

    assert route.provider == "qwen"
    assert route.upstream_model == "qwen2.5"


def test_reject_route_without_provider_prefix() -> None:
    try:
        resolve_route("qwen2.5", Settings())
    except RoutingError as error:
        assert "qwen/<model>" in str(error)
    else:
        raise AssertionError("Expected RoutingError")
