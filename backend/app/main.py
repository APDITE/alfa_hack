from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.routes import applications, auth, catalog, feed, health, meta


def create_app(settings: Settings | None = None) -> FastAPI:
    """App factory. Run with `uvicorn app.main:create_app --factory`."""
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="Smart Credit Cabinet API",
        description="Кредитный конвейер для МСБ: кабинет клиента и рабочее место банка.",
        version="0.1.0",
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    for module in (health, auth, catalog, applications, feed, meta):
        app.include_router(module.router, prefix="/api")
    return app
