from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from app.main.ioc import create_container
from app.main.settings import Settings
from app.presentation.applications import router as applications_router
from app.presentation.auth import router as auth_router
from app.presentation.catalog import router as catalog_router
from app.presentation.feed import router as feed_router
from app.presentation.health import router as health_router
from app.presentation.meta import router as meta_router


def create_app() -> FastAPI:
    container = create_container()
    settings = container.get(Settings)

    app = FastAPI(
        title="Smart Credit Cabinet API",
        description="Кредитный конвейер для МСБ: кабинет клиента и рабочее место банка.",
        version="0.1.0",
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
    )
    setup_dishka(container, app)
    for router in (
        health_router,
        auth_router,
        catalog_router,
        applications_router,
        feed_router,
        meta_router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
