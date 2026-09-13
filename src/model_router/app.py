from fastapi import FastAPI

from model_router.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Model Routing Efficiency Lab", version="0.1.0")
    app.state.settings = settings or get_settings()

    @app.get("/health")
    async def health() -> dict[str, object]:
        current: Settings = app.state.settings
        return {
            "status": "ok",
            "providers": {
                "qwen": {"configured": current.qwen_ready},
                "azure": {"configured": current.azure_ready},
                "judge": {"configured": current.judge_ready},
            },
            "content_persistence": current.router_store_content,
        }

    return app


app = create_app()
