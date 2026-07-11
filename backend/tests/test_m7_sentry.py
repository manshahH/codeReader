"""Sentry wiring: PII scrubbing is mandatory (this app handles credentials
and user answers, CLAUDE.md invariant 6), and a missing SENTRY_DSN must
never be treated as an error -- the common local-dev case.
"""

from __future__ import annotations

import os

import pytest
import sentry_sdk
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.core.sentry import init_sentry, scrub_event


def _base_settings_kwargs() -> dict[str, str]:
    return {
        "JWT_SECRET": "test-jwt-secret",
        "GITHUB_CLIENT_SECRET": "test-github-secret",
        "TOKEN_ENC_KEY": "test-token-encryption-key-32b",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
    }


def test_init_sentry_is_a_noop_without_a_dsn() -> None:
    settings = Settings(SENTRY_DSN="", **_base_settings_kwargs())
    init_sentry(settings)
    assert not sentry_sdk.is_initialized()


def test_scrub_event_strips_refresh_cookie_authorization_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_TOKEN_API_KEY", "sk-super-secret-value")
    event = {
        "request": {
            "headers": {
                "Cookie": "rt=raw-refresh-token-value; theme=dark",
                "Authorization": "Bearer eyFakeAccessToken",
                "Content-Type": "application/json",
            },
            "data": {"answer": {"text": "the user's private summarize answer"}},
        },
        "extra": {"jwt_secret": "leaked-jwt-secret", "safe_field": "keep-me"},
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {
                                "vars": {
                                    "password": "hunter2",
                                    "leaked_var": "sk-super-secret-value",
                                    "harmless": "keep-me-too",
                                }
                            }
                        ]
                    }
                }
            ]
        },
    }

    scrubbed = scrub_event(event, {})

    headers = scrubbed["request"]["headers"]
    assert "Authorization" not in headers
    assert headers["Cookie"] == "rt=[Filtered]; theme=dark"
    assert headers["Content-Type"] == "application/json"
    assert "data" not in scrubbed["request"]

    assert scrubbed["extra"]["jwt_secret"] == "[Filtered]"
    assert scrubbed["extra"]["safe_field"] == "keep-me"

    frame_vars = scrubbed["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
    assert frame_vars["password"] == "[Filtered]"
    # Caught by value, not by name: an env-secret value leaking into an
    # unrelated-looking local variable is still redacted.
    assert frame_vars["leaked_var"] == "[Filtered]"
    assert frame_vars["harmless"] == "keep-me-too"


@pytest.mark.asyncio
async def test_app_boots_and_serves_with_sentry_dsn_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        os.getenv("DATABASE_URL", "postgresql://codereader:codereader@127.0.0.1:5432/codereader"),
    )
    monkeypatch.setenv("REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-github-secret")
    monkeypatch.setenv("TOKEN_ENC_KEY", "test-token-encryption-key-32b")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("SENTRY_DSN", "")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    get_settings.cache_clear()
    assert not sentry_sdk.is_initialized()
    assert response.status_code in (200, 503)


@pytest.mark.asyncio
async def test_debug_sentry_endpoint_mounted_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        os.getenv("DATABASE_URL", "postgresql://codereader:codereader@127.0.0.1:5432/codereader"),
    )
    monkeypatch.setenv("REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-github-secret")
    monkeypatch.setenv("TOKEN_ENC_KEY", "test-token-encryption-key-32b")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("SENTRY_DSN", "")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "production")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/debug/sentry-test")

    get_settings.cache_clear()
    assert response.status_code == 404
