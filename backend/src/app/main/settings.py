from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    docs_enabled: bool = True
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    jwt_secret: str = "change-me"
