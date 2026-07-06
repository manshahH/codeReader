from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    DATABASE_URL: str = "postgresql://codereader:codereader@localhost:5432/codereader"
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET: str = Field(..., min_length=1)
    ACCESS_TOKEN_TTL: int = 900
    REFRESH_TOKEN_TTL_DAYS: int = 60
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = Field(..., min_length=1)
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/auth/github/callback"
    TOKEN_ENC_KEY: str = Field(..., min_length=1)
    APP_ORIGIN: str = "http://localhost:5173"
    ANTHROPIC_API_KEY: str = Field(..., min_length=1)
    GATE_MODEL: str = "gate-model-placeholder"
    GENERATOR_MODEL: str = "generator-model-placeholder"
    GRADER_TIMEOUT_S: int = 6
    SANDBOX_HOST: str = ""
    S3_BUCKET: str = "codereader-dev-events"
    S3_EVENTS_PREFIX: str = "events/"
    SENTRY_DSN: str = ""
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 60
    RATE_LIMIT_ATTEMPTS_PER_MINUTE: int = 10
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10

    @property
    def jwt_secrets(self) -> list[str]:
        return [secret.strip() for secret in self.JWT_SECRET.split(",") if secret.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
