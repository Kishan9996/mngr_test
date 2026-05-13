from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:3001"

    # Auth — access token short-lived; refresh token rotated
    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Database
    database_url: str = "sqlite:///./extraction.db"

    # CORS
    cors_origins: list[str] = ["http://localhost:3001"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
