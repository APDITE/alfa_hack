"""The API refuses to start outside development with a guessable JWT secret."""

import pytest

from app.config import Settings
from app.main import check_settings

DEFAULT_SECRET = Settings().jwt_secret


@pytest.mark.parametrize("secret", [DEFAULT_SECRET, "short-secret"])
def test_production_needs_a_real_secret(secret: str) -> None:
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        check_settings(Settings(app_env="production", jwt_secret=secret))


def test_production_with_a_long_secret_starts() -> None:
    check_settings(Settings(app_env="production", jwt_secret="x7Lq" * 10))


def test_development_keeps_the_default() -> None:
    check_settings(Settings(app_env="development", jwt_secret=DEFAULT_SECRET))
