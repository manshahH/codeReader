from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezones import local_date_for
from app.main import create_app
from app.models import StreakEvent, UserStats
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


async def _prime_session(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.get("/v1/session/today", headers=headers)
    assert response.status_code == 200


def _idem() -> str:
    return str(uuid.uuid4())


async def _streak_events(db_session: AsyncSession, user) -> list[StreakEvent]:
    query = (
        select(StreakEvent).where(StreakEvent.user_id == user.id).order_by(StreakEvent.created_at)
    )
    return list((await db_session.scalars(query)).all())


async def _submit(client: AsyncClient, headers: dict, exercise, *, reason_id: str = "a") -> dict:
    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": reason_id},
            "time_taken_ms": 1000,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_first_attempt_of_local_day_extends_streak_from_zero(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    body = await _submit(client, headers, exercise)

    assert body["streak"] == {"current": 1, "event": "extended"}
    events = await _streak_events(db_session, user)
    assert len(events) == 1
    assert events[0].event == "extended"
    assert events[0].from_value == 0
    assert events[0].to_value == 1


@pytest.mark.asyncio
async def test_second_attempt_same_local_day_does_not_double_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    ex1 = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    ex2 = await make_stb_exercise(db_session, concepts=["off-by-one"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    first = await _submit(client, headers, ex1)
    second = await _submit(client, headers, ex2)

    assert first["streak"] == {"current": 1, "event": "extended"}
    assert second["streak"] is None

    events = await _streak_events(db_session, user)
    assert len(events) == 1  # no second row for the same-day attempt


@pytest.mark.asyncio
async def test_attempt_the_day_after_a_streak_extends_it(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    today = local_date_for(user.timezone)
    db_session.add(
        UserStats(
            user_id=user.id,
            current_streak=5,
            longest_streak=5,
            last_active_local_date=today - dt.timedelta(days=1),
        ),
    )
    await db_session.flush()
    await db_session.commit()

    body = await _submit(client, headers, exercise)

    assert body["streak"] == {"current": 6, "event": "extended"}
    events = await _streak_events(db_session, user)
    assert len(events) == 1
    assert events[0].from_value == 5
    assert events[0].to_value == 6


@pytest.mark.asyncio
async def test_attempt_after_a_gap_resets_streak_to_one_but_keeps_longest(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    today = local_date_for(user.timezone)
    db_session.add(
        UserStats(
            user_id=user.id,
            current_streak=5,
            longest_streak=8,
            last_active_local_date=today - dt.timedelta(days=3),
        ),
    )
    await db_session.flush()
    await db_session.commit()

    body = await _submit(client, headers, exercise)

    assert body["streak"] == {"current": 1, "event": "reset"}
    stats = await db_session.get(UserStats, user.id)
    assert stats.longest_streak == 8  # untouched: 1 does not beat the prior best
    events = await _streak_events(db_session, user)
    assert len(events) == 1
    assert events[0].event == "reset"
    assert events[0].from_value == 5
    assert events[0].to_value == 1


@pytest.mark.asyncio
async def test_streak_transition_uses_user_local_timezone_not_utc(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Pacific/Kiritimati is UTC+14: local "today" can already be a day ahead
    # of UTC's date. Seed "yesterday" using the SAME helper the app uses, so
    # the assertion is about timezone wiring, not about a hardcoded date.
    user = await make_user(db_session, timezone="Pacific/Kiritimati")
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    today_local = local_date_for(user.timezone)
    db_session.add(
        UserStats(
            user_id=user.id,
            current_streak=3,
            longest_streak=3,
            last_active_local_date=today_local - dt.timedelta(days=1),
        ),
    )
    await db_session.flush()
    await db_session.commit()

    body = await _submit(client, headers, exercise)

    assert body["streak"] == {"current": 4, "event": "extended"}


def test_local_date_for_handles_the_timezone_boundary_deterministically() -> None:
    # 23:30 UTC on the 6th is already the 7th in UTC+2 (Paris, summer DST).
    just_before_utc_midnight = dt.datetime(2026, 7, 6, 23, 30, tzinfo=dt.UTC)
    assert local_date_for("UTC", just_before_utc_midnight) == dt.date(2026, 7, 6)
    assert local_date_for("Europe/Paris", just_before_utc_midnight) == dt.date(2026, 7, 7)

    # 00:30 UTC on the 7th is still the 6th in UTC-1 (Cape Verde).
    just_after_utc_midnight = dt.datetime(2026, 7, 7, 0, 30, tzinfo=dt.UTC)
    assert local_date_for("UTC", just_after_utc_midnight) == dt.date(2026, 7, 7)
    assert local_date_for("Atlantic/Cape_Verde", just_after_utc_midnight) == dt.date(2026, 7, 6)


@pytest.mark.asyncio
async def test_streak_audit_invariant_every_transition_writes_a_streak_event_row(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Invariant 5 (docs/05 section 8): every streak transition -> a
    streak_events row, and ONLY transitions -> a row (same-day resubmits
    don't add one).
    """
    user = await make_user(db_session)
    ex1 = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    ex2 = await make_stb_exercise(db_session, concepts=["off-by-one"])
    ex3 = await make_stb_exercise(db_session, concepts=["closure-late-binding"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    await _submit(client, headers, ex1)  # transition 1: extended 0 -> 1
    await _submit(client, headers, ex2)  # same local day: no transition

    today = local_date_for(user.timezone)
    stats = await db_session.get(UserStats, user.id)
    stats.last_active_local_date = today - dt.timedelta(days=1)
    await db_session.commit()

    await _submit(client, headers, ex3)  # transition 2: extended 1 -> 2

    events = await _streak_events(db_session, user)
    assert len(events) == 2
    assert [e.event for e in events] == ["extended", "extended"]
    assert [(e.from_value, e.to_value) for e in events] == [(0, 1), (1, 2)]
