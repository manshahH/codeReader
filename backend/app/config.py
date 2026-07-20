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
    # A3 reminders + weekly recap (docs/10; D-137). Nothing here can send while
    # EMAIL_SENDING_ENABLED is false: the jobs resolve their sender through the
    # same get_email_sender() the A2 routes use, so the off-switch is structural
    # for them too. The ledger still fills in, which is what makes the whole
    # flow walkable locally with nothing leaving the process.
    #
    # Retries are bounded by BOTH a count and a window. The window exists
    # because the second send-once layer is Resend's Idempotency-Key, which it
    # honours for 24 hours; outside that window a retry is no longer provably
    # safe, so we stop rather than risk a duplicate (D-137(4)).
    EMAIL_SEND_MAX_ATTEMPTS: int = 3
    EMAIL_SEND_RETRY_WINDOW_H: int = 24
    # Batching (D-137(10)). Sequential and paced, never a concurrent fan-out:
    # 200 simultaneous POSTs earns an immediate 429 and then we own a
    # retry-storm strictly worse than being slow in a background job nobody is
    # waiting on. 2/s is Resend's documented default rate limit. The per-tick
    # cap DEFERS rather than drops, which is only safe because reminder
    # eligibility runs to the end of the user's local day.
    EMAIL_JOB_BATCH_SIZE: int = 200
    EMAIL_MAX_SENDS_PER_TICK: int = 100
    EMAIL_SENDS_PER_SECOND: float = 2.0
    # The recap reports the ISO week that just ENDED, so Monday is the first
    # moment that week is complete; a Sunday-evening send would silently omit
    # Sunday. 09:00 is FIXED rather than the user's reminder time, so the two
    # cannot land in the same minute (0 = Monday, matching date.weekday()).
    RECAP_LOCAL_WEEKDAY: int = 0
    RECAP_LOCAL_HOUR: int = 9
    JOB_REMINDERS_INTERVAL_S: float = 300.0
    JOB_WEEKLY_RECAP_INTERVAL_S: float = 900.0
    # D-123. summarize is OFF (D-115) and this is the switch that enforces it.
    # It defaults FALSE, so summarize is excluded from sampling regardless of
    # what is in the exercises table: a live summarize row is no longer enough
    # to get one served. D-115 claimed the sampler already did this; it did not
    # (sessions/service.py used ALL_CANDIDATE_TYPES on the healthy-grader path),
    # and a live summarize row reached a real local session.
    # Turning this on re-enables the ONLY type with a per-answer LLM cost and
    # the only one that puts a grader on the hot path, which is the
    # prompt-injection surface invariant 6 exists for. Do not flip it without
    # re-reading D-115.
    SUMMARIZE_ENABLED: bool = False
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
