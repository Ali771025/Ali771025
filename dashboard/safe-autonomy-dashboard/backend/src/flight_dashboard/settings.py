from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DASH_", env_file=".env", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    host: str = "0.0.0.0"
    port: int = 8080
    database_path: Path = Path("./runtime/dashboard.db")
    jwt_secret: str = "development-only-change-this-secret"
    jwt_ttl_seconds: int = 8 * 60 * 60
    expert_username: str = "expert"
    expert_password: str = "expert-dev"
    manager_username: str = "manager"
    manager_password: str = "manager-dev"
    udp_host: str = "0.0.0.0"
    udp_port: int = 15010
    tcp_host: str = "0.0.0.0"
    tcp_port: int = 15011
    ingest_shared_secret: str = ""
    ws_queue_size: int = Field(default=128, ge=16, le=4096)
    telemetry_sample_hz: float = Field(default=2.0, ge=0.1, le=20)
    control_mode: Literal["disabled", "simulation", "gateway"] = "simulation"
    control_require_dual_approval: bool = True
    control_gateway_url: str = ""
    control_gateway_secret: str = ""
    control_intent_ttl_seconds: int = 30
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("jwt_secret")
    @classmethod
    def production_secret_is_not_default(cls, value: str, info):
        if info.data.get("env") == "production":
            if len(value) < 32:
                raise ValueError("DASH_JWT_SECRET must contain at least 32 characters in production")
            if value == "development-only-change-this-secret":
                raise ValueError("DASH_JWT_SECRET must be changed from default in production")
        return value

    @field_validator("expert_password", "manager_password")
    @classmethod
    def production_passwords_must_change(cls, value: str, info):
        if info.data.get("env") == "production" and value in {"expert-dev", "manager-dev"}:
            raise ValueError("Default passwords must be changed in production")
        return value

    @property
    def cors_origins(self) -> list[str]:
        origins = [item.strip() for item in self.allowed_origins.split(",") if item.strip()]
        if self.env == "production" and not origins:
            raise ValueError("DASH_ALLOWED_ORIGINS must be configured in production")
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()

