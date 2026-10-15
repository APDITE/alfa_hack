from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from app.main.ioc import create_container
from app.main.settings import Settings
from app.presentation.health import router as health_router


def create_app() -> FastAPI:
    container = create_container()
    settings = container.get(Settings)

    app = FastAPI(
        title="Hackathon API",
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
    )
    setup_dishka(container, app)
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
