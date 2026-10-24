from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.products import load_products
from app.routes import applications, auth, catalog, feed, health, meta, ops

_DEV_SECRET_PREFIX = "dev-only"


def check_settings(settings: Settings) -> None:
    """Refuse to start outside development with the default or a short JWT secret."""
    if settings.app_env == "development":
        return
    if settings.jwt_secret.startswith(_DEV_SECRET_PREFIX) or len(settings.jwt_secret) < 32:
        raise RuntimeError(
            f"APP_ENV={settings.app_env}: set JWT_SECRET to a random value of 32+ characters"
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    """App factory. Run with `uvicorn app.main:create_app --factory`."""
    settings = settings or Settings()
    check_settings(settings)
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="Smart Credit Cabinet API",
        description="Кредитный конвейер для МСБ: кабинет клиента и рабочее место банка.",
        version="1.0.0",
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.products = load_products(Path(settings.products_path))

    for module in (health, auth, catalog, applications, feed, meta, ops):
        app.include_router(module.router, prefix="/api")
    # Prometheus scrapes the backend directly; nginx does not proxy /metrics.
    app.include_router(ops.metrics_router)
    return app
