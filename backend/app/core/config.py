from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Smart Report Builder & NL2SQL"
    environment: Literal["local", "dev", "stage", "production"] = "local"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@postgres:5432/nl2sql_reporting",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", validation_alias="REDIS_URL")
    frontend_origin: str = Field(default="http://localhost:5173", validation_alias="FRONTEND_ORIGIN")

    access_token_expire_minutes: int = 60
    refresh_token_expire_minutes: int = 60 * 24 * 14
    jwt_secret_key: str = Field(default="change-me-in-production", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"

    password_min_length: int = 10
    captcha_failed_attempt_threshold: int = 3
    default_timezone: str = "Asia/Tehran"
    default_locale: str = "fa-IR"
    auto_create_db: bool = Field(default=True, validation_alias="AUTO_CREATE_DB")
    seed_demo_data: bool = Field(default=True, validation_alias="SEED_DEMO_DATA")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
