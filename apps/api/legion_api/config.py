from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-secret-change-me-dev-only-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+psycopg://legion:legion@localhost:5432/legion"
    redis_url: str = ""  # optional; enables shared rate limiting across API replicas
    jwt_secret: str = _DEV_SECRET
    access_token_minutes: int = 60 * 12
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000"
    login_attempts_per_window: int = 10
    login_window_seconds: int = 300

    data_provider: Literal["demo", "alpaca", "polygon"] = "demo"
    alpaca_api_key_id: str = ""
    alpaca_api_secret_key: str = ""
    alpaca_feed: str = "iex"
    polygon_api_key: str = ""
    polygon_base_url: str = "https://api.polygon.io"
    bars_cache_seconds: int = 300

    @model_validator(mode="after")
    def _prod_guards(self) -> Settings:
        if self.env == "prod":
            if self.jwt_secret == _DEV_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters in prod")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
