from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/gateway"
    REDIS_URL: str = "redis://localhost:6379"
    STRIPE_WEBHOOK_SECRET: str = "whsec_test_secret"
    GROQ_API_KEY: str = "gsk_placeholder"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
