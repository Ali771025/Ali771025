"""Platform configuration [TECH]."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "QORA Platform"
    DATABASE_URL: str = "sqlite:///./qora_platform.db"
    SECRET_KEY: str = "qora-platform-dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    CORS_ORIGINS: str = "*"

    # Discovery ranking weights: eight PRD signals, editable by platform admins [TECH].
    RANK_W_INTENT: float = 0.25
    RANK_W_OUTCOME: float = 0.18
    RANK_W_PERSONAL_FIT: float = 0.12
    RANK_W_TRUST: float = 0.15
    RANK_W_FRESHNESS: float = 0.10
    RANK_W_EXPLORATION: float = 0.05
    RANK_W_SATISFACTION: float = 0.05
    RANK_W_REPEAT_USE: float = 0.10

    MODEL_PROVIDER: str = "local"  # local | openai_compatible
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"


settings = Settings()
