from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM provider — "grok" (default) or "claude"
    llm_provider: str = "grok"

    # Anthropic / Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # xAI / Grok  (only required when llm_provider=grok)
    grok_api_key: str = ""
    grok_model: str = "grok-3"

    # Google Calendar
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/calendar/auth/google/callback"

    # Outlook
    outlook_client_id: str = ""
    outlook_client_secret: str = ""
    outlook_tenant_id: str = "common"
    outlook_redirect_uri: str = "http://localhost:8000/api/calendar/auth/outlook/callback"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:3000"
    scheduling_lookahead_days: int = 7
    default_work_start: str = "09:00"
    default_work_end: str = "17:00"
    default_slot_duration_minutes: int = 60
    default_timezone: str = "UTC"

    # Auth
    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    jwt_expire_days: int = 30

    # Database
    database_url: str = "sqlite:///./chatbot.db"

    # Cache — leave empty to fall back to in-memory TTL cache
    redis_url: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
