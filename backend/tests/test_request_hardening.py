"""Red-team request-layer hardening (the three mediums):

M1  an UNAUTHENTICATED flood of POST /v1/attempts is rate-limited by IP (the
    per-user attempts limit runs after auth, so anonymous requests used to hit
    no limiter at all).
M2  an unhandled 500 returns the uniform JSON error shape + request_id +
    security headers, and never leaks the exception.
M3  a client-supplied X-Request-ID is sanitized (injection-shaped values are
    replaced with a server-generated id; a well-formed one is honored).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app
from tests.factories_m4 import (
    clean_redis,  # noqa: F401 (autouse)
    m4_env,  # noqa: F401 (autouse)
)


@pytest.mark.asyncio
async def test_unauthenticated_attempts_flood_is_rate_limited_by_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M1: POST /v1/attempts with a missing/garbage token is rejected at auth
    (401) but used to never touch a rate limiter -- a free flood on the write
    endpoint. The default middleware now applies an IP limit to it for
    unauthenticated requests, so the flood trips 429 (not an endless 401)."""
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "2")
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    body = {
        "exercise_id": "00000000-0000-0000-0000-000000000000",
        "exercise_version": 1,
        "answer": {"choice_id": "a"},
    }
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        statuses = [
            (
                await client.post(
                    "/v1/attempts",
                    headers={"Authorization": "Bearer garbage", "Idempotency-Key": f"k{i}"},
                    json=body,
                )
            ).status_code
            for i in range(3)
        ]

    get_settings.cache_clear()
    # First two are rejected at auth (no valid token); the third is stopped by
    # the IP rate limiter BEFORE auth -- proving anonymous floods are capped.
    assert statuses == [401, 401, 429]


@pytest.mark.asyncio
async def test_authenticated_attempts_are_not_double_limited_by_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M1 corollary: an AUTHENTICATED POST /attempts must still defer to its own
    per-user limit and not be caught by the default IP limit. A valid-token
    request keys on user, so the default middleware skips it -- even with the
    default limit set to 1, two authenticated attempts are not blocked by the
    default (they are governed by the 10/min per-user limit instead)."""
    from app.db import create_engine, create_session_factory
    from tests.factories_m4 import auth_headers, make_stb_exercise, make_user

    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "1")
    monkeypatch.setenv("RATE_LIMIT_ATTEMPTS_PER_MINUTE", "10")
    get_settings.cache_clear()

    engine = create_engine()
    async with create_session_factory(engine)() as setup:
        user = await make_user(setup)
        ex1 = await make_stb_exercise(setup, concepts=["mutable-default-arg"])
        ex2 = await make_stb_exercise(setup, concepts=["off-by-one"])
    await engine.dispose()
    headers = auth_headers(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        await client.get("/v1/session/today", headers=headers)
        first = await client.post(
            "/v1/attempts",
            headers={**headers, "Idempotency-Key": "a1"},
            json={
                "exercise_id": str(ex1.id),
                "exercise_version": ex1.version,
                "answer": {"line": 1, "reason_id": "a"},
            },
        )
        second = await client.post(
            "/v1/attempts",
            headers={**headers, "Idempotency-Key": "a2"},
            json={
                "exercise_id": str(ex2.id),
                "exercise_version": ex2.version,
                "answer": {"line": 1, "reason_id": "a"},
            },
        )

    get_settings.cache_clear()
    # Neither is a 429: the default limit of 1 did not engage for the
    # authenticated write path (the per-user attempts limit governs it).
    assert first.status_code == 200
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_unhandled_500_returns_uniform_json_shape_headers_and_no_stacktrace() -> None:
    """M2: the debug endpoint raises an unhandled RuntimeError. The response
    must be the uniform JSON error (code 'internal') with a request_id and the
    security headers, and must NOT contain the exception text/traceback."""
    app = create_app()
    # raise_app_exceptions=False so the transport returns the 500 response
    # instead of re-raising, exactly as a real ASGI server does to a client.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        response = await client.get("/v1/debug/sentry-test")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error"]["code"] == "internal"
    assert body["error"]["request_id"]
    # Security headers present on the error path too (they were missing before).
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "X-Request-ID" in response.headers
    # The exception is never leaked to the client.
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
    assert "Sentry backend verification" not in response.text


@pytest.mark.asyncio
async def test_client_supplied_request_id_is_sanitized() -> None:
    """M3: an injection-shaped X-Request-ID (spaces/newlines/`=`) is dropped in
    favor of a server-generated id, so it can never forge structured-log
    fields; a well-formed value is still honored for trace propagation."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        injected = await client.get(
            "/healthz",
            headers={"X-Request-ID": "evil id with spaces and fake_field=1"},
        )
        wellformed = await client.get(
            "/healthz",
            headers={"X-Request-ID": "trace-abc123_DEF"},
        )

    # The malicious value is NOT reflected; a fresh server id is used instead.
    assert injected.headers["X-Request-ID"] != "evil id with spaces and fake_field=1"
    assert injected.headers["X-Request-ID"].startswith("req_")
    # A safe, well-formed id IS honored (a trusted upstream can propagate it).
    assert wellformed.headers["X-Request-ID"] == "trace-abc123_DEF"
