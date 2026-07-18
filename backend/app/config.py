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
    # Optional (mirrors pipeline/config.py's PipelineSettings, D-44): this
    # project is OpenAI-only by default (GRADER_PROVIDER="openai" below).
    # Whichever grader provider is actually selected has its key validated
    # lazily at first use in attempts/grader_client.py, not required here --
    # requiring ANTHROPIC_API_KEY unconditionally blocked constructing
    # Settings at all on an OpenAI-only deploy with no Anthropic key.
    ANTHROPIC_API_KEY: str = ""
    GATE_MODEL: str = "gate-model-placeholder"
    GENERATOR_MODEL: str = "generator-model-placeholder"
    # D-80: pipeline-only (PipelineSettings owns the real behavior, D-33);
    # mirrored here so the shared root .env.example stays drift-free against
    # Settings, same as GATE_MODEL/GENERATOR_MODEL. Empty = STB routing OFF.
    GENERATOR_MODEL_STB: str = ""
    # This project is OpenAI-only (D-43/D-44); tracked defaults must point
    # there so an un-overridden deploy reaches a real provider instead of
    # silently trying Anthropic with an empty key and stranding every
    # summarize attempt in grading_pending forever.
    GRADER_PROVIDER: str = "openai"
    GRADER_MODEL: str = "grader-model-placeholder"
    OPENAI_API_KEY: str = ""
    GRADER_TIMEOUT_S: int = 6
    SANDBOX_HOST: str = ""
    S3_BUCKET: str = "codereader-dev-events"
    S3_EVENTS_PREFIX: str = "events/"
    EVENTS_LOCAL_DIR: str = "data/events"
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 60
    RATE_LIMIT_ATTEMPTS_PER_MINUTE: int = 10
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    # Number of trusted reverse proxies (e.g. the LB) directly in front of
    # this API instance. Per-IP rate limiting reads the X-Forwarded-For hop
    # this many positions from the right, never the client-suppliable
    # leftmost entry. 0 = no trusted proxy; use the raw TCP peer. See
    # docs/ops-runbook.md for the required proxy configuration.
    TRUSTED_PROXY_COUNT: int = 1
    # Shared-secret gate for GET /admin/metrics (see docs/07 D-entry: a
    # pragmatic M7 placeholder, not the separate internal admin app docs/05
    # section 7 describes). Empty = endpoint disabled (404).
    ADMIN_METRICS_TOKEN: str = ""
    # M8's private-beta gate (users.beta_allowed / beta_invites) defaults OFF
    # for public launch (D-92): a switch, not a wall. beta_allowed/beta_invites/
    # _apply_beta_invite stay wired and populated regardless -- flipping this
    # back to true restores the exact prior gate with no other change.
    BETA_GATE_ENABLED: bool = False
    # A1 streak safety net (docs/10; D-116). Freezes are a forgiveness
    # mechanic, not a currency to hoard: START=2 because Duolingo's A/B found
    # 2 beat 1 while 3 did not beat 2, and MAX==START so the balance is a
    # buffer that refills rather than a score that grows. EARN_EVERY is
    # measured in consecutive active days. REPAIR_WINDOW_H bounds how long
    # after a reset the lost streak can still be earned back.
    STREAK_FREEZE_START: int = 2
    STREAK_FREEZE_MAX: int = 2
    STREAK_FREEZE_EARN_EVERY: int = 10
    STREAK_REPAIR_WINDOW_H: int = 48
    # A2 email capture (docs/10; D-120). EMAIL_SENDING_ENABLED is a HARD
    # off-switch and defaults OFF: with it false the Resend client short-circuits
    # before constructing any request, so local dev and the test suite can never
    # make a network call or spend a send. Production sets it true explicitly.
    EMAIL_SENDING_ENABLED: bool = False
    # Optional, exactly like ANTHROPIC_API_KEY above (D-44): validated LAZILY at
    # first send in email/resend_client.py, never required here -- requiring it
    # unconditionally would block constructing Settings at all on any deploy
    # that does not send email (and on every test run).
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "CodeReader <no-reply@codereader.dev>"
    EMAIL_VERIFICATION_TTL_H: int = 24
    # Throttle, two layers with deliberately different scopes (see
    # email/service.py::_enforce_send_throttle). The cooldown is a per-ADDRESS
    # floor between sends and is what the UI's disabled "Resend" timer mirrors;
    # it is NOT per-user, because that would make a user wait to correct a typo.
    # The hourly cap is per user AND per address: per-user alone lets one
    # account walk an address list, per-address alone lets many accounts
    # converge on one mailbox.
    EMAIL_VERIFICATION_RESEND_COOLDOWN_S: int = 60
    EMAIL_VERIFICATION_SENDS_PER_HOUR: int = 5
    JOBS_ENABLED: bool = True
    JOB_GRADING_RETRY_INTERVAL_S: float = 30.0
    JOB_PERCENTILES_INTERVAL_S: float = 3600.0
    JOB_PARTITIONS_INTERVAL_S: float = 86400.0
    CODEREADER_ALLOW_SEED: bool = False

    @property
    def jwt_secrets(self) -> list[str]:
        return [secret.strip() for secret in self.JWT_SECRET.split(",") if secret.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
