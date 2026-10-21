from collections.abc import Callable, Iterator

import pytest
from app.config import Settings
from app.db import Base
from app.main import create_app
from app.seed import seed_all
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-at-least-32-bytes-long-0001",
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    """App on a fresh in-memory SQLite database with demo data loaded."""
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        seed_all(session, settings)
    yield app
    app.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def login_as(client: TestClient) -> LoginAs:
    """Authorization header for a seeded test account (password equals login)."""

    def _login(user: str) -> dict[str, str]:
        response = client.post("/api/auth/login", json={"login": user, "password": user})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login
