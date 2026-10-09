"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "QORA — Consumer AI Service Network"
    DATABASE_URL: str = "sqlite:///./qora.db"
    SECRET_KEY: str = "qora-dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    CORS_ORIGINS: str = "*"
    PLATFORM_FEE_PERCENT: int = 10


settings = Settings()
