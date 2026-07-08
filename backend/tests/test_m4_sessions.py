from __future__ import annotations

import datetime as dt

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.main import create_app
from app.models import DailySession
from app.sessions.sampler import difficulty_band
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401 (autouse fixture, must be imported to activate)
    clean_redis,  # noqa: F401 (autouse fixture, must be imported to activate)
    m4_env,  # noqa: F401 (autouse fixture, must be imported to activate)
    make_stb_exercise,
    make_trace_exercise,
    make_user,
)


def _walk_keys(node: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        keys.update(node.keys())
        for value in node.values():
            keys |= _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            keys |= _walk_keys(item)
    return keys


async def _seed_pool(db_session: AsyncSession) -> None:
    await make_stb_exercise(db_session, concepts=["mutable-default-arg"], difficulty_authored=3)
    await make_trace_exercise(db_session, concepts=["off-by-one"], difficulty_authored=5)
    await make_stb_exercise(db_session, concepts=["closure-late-binding"], difficulty_authored=4)
    await make_trace_exercise(db_session, concepts=["aliasing-vs-copy"], difficulty_authored=6)
    await make_stb_exercise(db_session, concepts=["shared-class-attribute"], difficulty_authored=2)
    await make_trace_exercise(
        db_session,
        concepts=["concurrency-conceptual"],
        difficulty_authored=9,
    )


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_answer_key_leak_session_response_has_no_grading_or_explanation_keys(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Invariant 1 (docs/05 section 8): no `grading`/`explanation` key anywhere
    in the actual wire response body, across every slot including the boss.
    """
    user = await make_user(db_session)
    await _seed_pool(db_session)

    response = await client.get("/v1/session/today", headers=auth_headers(user))

    assert response.status_code == 200
    body = response.json()
    assert len(body["exercises"]) >= 3
    assert any(exercise["is_boss"] for exercise in body["exercises"])

    keys = _walk_keys(body)
    assert "grading" not in keys
    assert "explanation" not in keys


@pytest.mark.asyncio
async def test_session_builds_persists_and_reopen_returns_identical_session(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await _seed_pool(db_session)

    first = await client.get("/v1/session/today", headers=auth_headers(user))
    second = await client.get("/v1/session/today", headers=auth_headers(user))

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()

    today = dt.datetime.now(dt.UTC).date()
    row = await db_session.get(DailySession, (user.id, today))
    assert row is not None
    assert len(row.exercise_list) == len(first.json()["exercises"])


@pytest.mark.asyncio
async def test_redis_flush_does_not_resample_falls_back_to_daily_sessions_row(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await _seed_pool(db_session)

    first = await client.get("/v1/session/today", headers=auth_headers(user))
    assert first.status_code == 200

    redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()

    second = await client.get("/v1/session/today", headers=auth_headers(user))
    assert second.status_code == 200
    assert first.json() == second.json()


@pytest.mark.asyncio
async def test_session_slot_count_is_within_3_to_5_bounds(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await _seed_pool(db_session)

    response = await client.get("/v1/session/today", headers=auth_headers(user))

    exercises = response.json()["exercises"]
    assert 3 <= len(exercises) <= 5
    boss_slots = [e for e in exercises if e["is_boss"]]
    assert len(boss_slots) == 1
    assert boss_slots[0]["difficulty_band"] == "boss"
    slot_numbers = [e["slot"] for e in exercises]
    assert slot_numbers == sorted(slot_numbers)
    assert slot_numbers[-1] == boss_slots[0]["slot"]


@pytest.mark.asyncio
async def test_session_only_pulls_live_exercises_via_exercises_current(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await make_stb_exercise(db_session, concepts=["mutable-default-arg"], status="draft")
    await make_stb_exercise(db_session, concepts=["off-by-one"], status="in_review")
    live = await make_stb_exercise(db_session, concepts=["closure-late-binding"], status="live")

    response = await client.get("/v1/session/today", headers=auth_headers(user))

    exercise_ids = {e["exercise_id"] for e in response.json()["exercises"]}
    assert exercise_ids == {str(live.id)}


def test_difficulty_band_mapping() -> None:
    assert difficulty_band(1, is_boss=False) == "easy"
    assert difficulty_band(3, is_boss=False) == "easy"
    assert difficulty_band(4, is_boss=False) == "medium"
    assert difficulty_band(6, is_boss=False) == "medium"
    assert difficulty_band(7, is_boss=False) == "hard"
    assert difficulty_band(10, is_boss=False) == "hard"
    assert difficulty_band(1, is_boss=True) == "boss"
    assert difficulty_band(10, is_boss=True) == "boss"
