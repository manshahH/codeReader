"""M7 hardening: rate limiting applied to ALL routes (not just auth/attempts),
the X-Forwarded-For leftmost-spoofing bypass closed, and the POST /attempts
concurrency fix (Redis idempotency-key reservation + Postgres advisory lock)
proving exactly one attempt row survives a genuine concurrent double submit.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.network import resolve_client_ip
from app.db import create_engine, create_session_factory
from app.main import create_app
from app.models import Attempt, StreakEvent, UserStats
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)


def _idem() -> str:
    return str(uuid.uuid4())


def _scope_request(
    headers: list[tuple[bytes, bytes]],
    client_host: str = "198.51.100.7",
) -> Request:
    scope = {
        "type": "http",
        "headers": headers,
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_resolve_client_ip_trusts_only_the_configured_rightmost_hops() -> None:
    headers = [(b"x-forwarded-for", b"1.2.3.4, 10.0.0.9")]
    request = _scope_request(headers)

    # A real trusted proxy appends the peer IP it observed to the RIGHT end;
    # only that rightmost hop is safe to trust. The leftmost entry is
    # whatever the client itself sent and is fully attacker-controlled.
    assert resolve_client_ip(request, trusted_proxy_count=1) == "10.0.0.9"

    # No trusted proxy configured: the header must be ignored entirely and
    # the direct TCP peer used, never a client-suppliable value.
    assert resolve_client_ip(request, trusted_proxy_count=0) == "198.51.100.7"


@pytest.mark.asyncio
async def test_auth_rate_limit_ignores_spoofable_leftmost_xff_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes the bypass: before the fix, `_client_ip` read the leftmost
    (client-controlled) X-Forwarded-For entry, so an attacker rotating that
    value got a fresh rate-limit bucket key on every request and the 10/min
    auth limit never engaged. Each request below claims a DIFFERENT
    leftmost IP but the SAME rightmost hop -- what a real trusted proxy
    would append after observing the same physical client each time -- and
    the limit must still trip on the third request.
    """
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-github-client-secret")
    monkeypatch.setenv("TOKEN_ENC_KEY", "test-token-enc-key-32-byte-value")
    monkeypatch.setenv("APP_ORIGIN", "https://app.example")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "2")
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    get_settings.cache_clear()

    from redis.asyncio import Redis

    redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        responses = [
            await client.get(
                "/v1/auth/github/start",
                headers={"X-Forwarded-For": f"203.0.113.{i}, 10.0.0.9"},
                follow_redirects=False,
            )
            for i in range(1, 4)
        ]

    get_settings.cache_clear()
    assert [r.status_code for r in responses] == [302, 302, 429]
    assert responses[-1].json()["error"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_default_rate_limit_applies_to_routes_with_no_specific_limit(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /me/stats has no route-specific limit (only auth and POST
    /attempts do) -- before the default middleware existed, it had NO rate
    limiting at all. Also asserts X-RateLimit-* headers are present on the
    successful response, not just the 429.
    """
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_PER_MINUTE", "1")
    get_settings.cache_clear()

    user = await make_user(db_session)
    headers = auth_headers(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        first = await client.get("/v1/me/stats", headers=headers)
        second = await client.get("/v1/me/stats", headers=headers)

    get_settings.cache_clear()
    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "1"
    assert first.headers["X-RateLimit-Remaining"] == "0"
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"
    assert "Retry-After" in second.headers


@pytest.mark.asyncio
async def test_idempotent_replay_carries_rate_limit_headers(
    db_session: AsyncSession,
) -> None:
    """Docs/05 section 1: "Headers on every response" -- a pure replay
    (cache hit) previously skipped the rate-limit check entirely and shipped
    with no X-RateLimit-* headers at all.
    """
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        await client.get("/v1/session/today", headers=headers)
        idem_key = _idem()
        body = {
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        }
        first = await client.post(
            "/v1/attempts",
            headers={**headers, "Idempotency-Key": idem_key},
            json=body,
        )
        second = await client.post(
            "/v1/attempts",
            headers={**headers, "Idempotency-Key": idem_key},
            json=body,
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers.get("X-Idempotent-Replay") == "true"
    assert "X-RateLimit-Limit" in second.headers
    assert "X-RateLimit-Remaining" in second.headers


async def _attempt_row_count(user_id: uuid.UUID) -> int:
    engine = create_engine()
    try:
        async with create_session_factory(engine)() as check_db:
            return (
                await check_db.execute(
                    select(func.count()).select_from(Attempt).where(Attempt.user_id == user_id),
                )
            ).scalar_one()
    finally:
        await engine.dispose()


async def _user_stats(user_id: uuid.UUID) -> UserStats | None:
    engine = create_engine()
    try:
        async with create_session_factory(engine)() as check_db:
            return await check_db.get(UserStats, user_id)
    finally:
        await engine.dispose()


async def _streak_event_count(user_id: uuid.UUID) -> int:
    engine = create_engine()
    try:
        async with create_session_factory(engine)() as check_db:
            return (
                await check_db.execute(
                    select(func.count())
                    .select_from(StreakEvent)
                    .where(StreakEvent.user_id == user_id),
                )
            ).scalar_one()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_first_of_day_submits_of_different_exercises_write_one_streak_event(
    db_session: AsyncSession,
) -> None:
    """H1/D-104: the streak transition + total_attempts are per-USER, but the
    advisory lock used to be keyed per-EXERCISE, so two concurrent first-of-day
    submits of DIFFERENT exercises never serialized -- both saw last_active !=
    today, both took the "extended" branch, and wrote TWO streak_events rows
    (invariant 5: one transition must write exactly one row) plus a lost
    total_attempts increment. asyncio.gather fires two REAL concurrent requests
    for two DIFFERENT exercises as the user's first activity of the day; the
    per-(user, day) advisory lock must serialize them into exactly one
    transition, and the partial unique index is the DB backstop underneath.
    """
    user = await make_user(db_session)
    ex1 = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    ex2 = await make_stb_exercise(db_session, concepts=["off-by-one"])
    headers = auth_headers(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        served = {
            e["exercise_id"]
            for e in (await client.get("/v1/session/today", headers=headers)).json()["exercises"]
        }
        assert {str(ex1.id), str(ex2.id)} <= served, "both exercises must be in the session"

        def _body(ex: object) -> dict:
            return {
                "exercise_id": str(ex.id),
                "exercise_version": ex.version,
                "answer": {"line": 1, "reason_id": "a"},
                "time_taken_ms": 1000,
            }

        responses = await asyncio.gather(
            client.post(
                "/v1/attempts", headers={**headers, "Idempotency-Key": _idem()}, json=_body(ex1),
            ),
            client.post(
                "/v1/attempts", headers={**headers, "Idempotency-Key": _idem()}, json=_body(ex2),
            ),
        )

    # Both submissions succeed (different exercises -- no already_attempted).
    assert sorted(r.status_code for r in responses) == [200, 200]
    # Exactly ONE streak transition row for the day (invariant 5), never two.
    assert await _streak_event_count(user.id) == 1
    # No lost update: both submissions counted, and the streak advanced once.
    stats = await _user_stats(user.id)
    assert stats is not None
    assert stats.total_attempts == 2
    assert stats.current_streak == 1


@pytest.mark.asyncio
async def test_streak_events_unique_index_rejects_a_second_daily_transition(
    db_session: AsyncSession,
) -> None:
    """The un-raceable DB backstop (H1/D-104, migration 0007): independent of
    the advisory lock, the partial unique index refuses a SECOND
    extended/reset row for the same (user_id, local_date). 'repaired' and the
    other non-transition event kinds stay unconstrained and may co-occur."""
    user = await make_user(db_session)
    user_id = user.id
    day = dt.date(2026, 7, 12)

    # Isolated sessions per step: a failed commit poisons its own session, so
    # each operation gets a fresh one (the same pattern as the count helpers).
    engine = create_engine()
    try:
        async with create_session_factory(engine)() as session:
            session.add(
                StreakEvent(
                    user_id=user_id, event="extended", from_value=0, to_value=1, local_date=day,
                ),
            )
            await session.commit()

        # A second transition on the same local day violates the partial index.
        async with create_session_factory(engine)() as session:
            session.add(
                StreakEvent(
                    user_id=user_id, event="reset", from_value=1, to_value=1, local_date=day,
                ),
            )
            with pytest.raises(IntegrityError):
                await session.commit()

        # A non-transition event on the same day is unconstrained (allowed).
        async with create_session_factory(engine)() as session:
            session.add(
                StreakEvent(
                    user_id=user_id, event="repaired", from_value=1, to_value=1, local_date=day,
                ),
            )
            await session.commit()  # must not raise
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_double_submit_same_idempotency_key_creates_exactly_one_attempt(
    db_session: AsyncSession,
) -> None:
    """The audit's headline concurrency bug: two concurrent POSTs for the
    same exercise (two tabs, or a network retry racing the original) used
    to both miss the idempotency cache, both pass the already-attempted
    SELECT (no row lock), and both INSERT -- a duplicate attempts row and a
    lost update on total_attempts. asyncio.gather fires two REAL concurrent
    requests (not sequential awaits) with the SAME Idempotency-Key; the
    Redis reservation + Postgres advisory lock must serialize them into
    exactly one persisted attempt either way.
    """
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        await client.get("/v1/session/today", headers=headers)
        idem_key = _idem()
        body = {
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        }
        responses = await asyncio.gather(
            client.post(
                "/v1/attempts",
                headers={**headers, "Idempotency-Key": idem_key},
                json=body,
            ),
            client.post(
                "/v1/attempts",
                headers={**headers, "Idempotency-Key": idem_key},
                json=body,
            ),
        )

    assert [r.status_code for r in responses] == [200, 200]
    attempt_ids = {r.json()["attempt_id"] for r in responses}
    assert len(attempt_ids) == 1, "both concurrent requests must replay the SAME attempt"

    assert await _attempt_row_count(user.id) == 1
    stats = await _user_stats(user.id)
    assert stats is not None
    assert stats.total_attempts == 1


@pytest.mark.asyncio
async def test_concurrent_double_submit_different_idempotency_keys_still_one_attempt(
    db_session: AsyncSession,
) -> None:
    """The "two tabs" variant: each tab independently generates its own
    Idempotency-Key when it serves the exercise, so a same-key reservation
    alone cannot serialize them. The Postgres advisory lock on
    (user_id, exercise_id, session_date) is the backstop that must still
    enforce the one-attempt-per-exercise-per-session rule regardless of
    which Idempotency-Key each concurrent request used.
    """
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        await client.get("/v1/session/today", headers=headers)
        body = {
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        }
        responses = await asyncio.gather(
            client.post(
                "/v1/attempts",
                headers={**headers, "Idempotency-Key": _idem()},
                json=body,
            ),
            client.post(
                "/v1/attempts",
                headers={**headers, "Idempotency-Key": _idem()},
                json=body,
            ),
        )

    statuses = sorted(r.status_code for r in responses)
    # One wins with 200; the loser observes the winner's committed row via
    # the already-attempted check and correctly 409s -- it is NOT a replay
    # (different Idempotency-Key), so a conflict response is the correct
    # outcome here, not a silent duplicate.
    assert statuses == [200, 409]

    assert await _attempt_row_count(user.id) == 1
    stats = await _user_stats(user.id)
    assert stats is not None
    assert stats.total_attempts == 1
