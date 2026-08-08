"""
Application configuration using Pydantic Settings.
Values are loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    from src.compat.pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "Social Listening Multi-Agent Platform"
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    api_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/social_listening")
    # SQLite dung cho API dong bo (routes.py) - luu ket qua crawl/pipeline that,
    # doc lap voi database_url (danh cho Postgres/production sau nay, xem docker-compose.yml).
    sqlite_path: str = Field(default="data/social_listening.db")

    # --- LLM Provider (Google Gemini) ---
    gemini_api_key: str = Field(default="")
    llm_model: str = Field(default="gemini-2.5-flash")
    llm_max_tokens: int = Field(default=1024)

    # --- Pipeline ---
    pipeline_interval_minutes: int = Field(default=20)   # 15-30 min cycle per PRD
    negative_alert_threshold: int = Field(default=10)    # posts/pain point before alert
    enable_scheduler: bool = Field(default=True)         # tat trong test de khong crawl mang that

    # --- Crawlers ---
    enabled_sources: list[str] = Field(default=["google_play", "app_store", "linkedin"])

    # --- Notifications ---
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")

    # --- Respond / Report (SMCC) ---
    sla_response_hours: int = Field(default=48)  # moc SLA xu ly pain point, dung cho GET /report/summary


@lru_cache
def get_settings() -> Settings:
    return Settings()
