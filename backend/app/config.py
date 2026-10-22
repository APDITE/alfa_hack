from typing import Annotated

from fastapi import Depends, Request
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    docs_enabled: bool = True
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    jwt_secret: str = "dev-only-secret-change-me-in-production-0001"
    jwt_ttl_minutes: int = 12 * 60
    bcrypt_rounds: int = 12
    products_path: str = "config/products.yaml"
    demo_data_path: str = "config/demo_companies.yaml"


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]
