"""pull_exercise: the working code path to take a bad live exercise out of
circulation (audit FIX 2). docs/00's #1 kill risk is one wrong answer going
viral; the mitigation is a fast pull that also purges the session caches, or
users keep being served the bad exercise for up to 36h.
"""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exercises.service import pull_exercise
from app.main import create_app
from app.models import DailySession, Exercise
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401 (autouse fixture, must be imported to activate)
    clean_redis,  # noqa: F401 (autouse fixture, must be imported to activate)
    m4_env,  # noqa: F401 (autouse fixture, must be imported to activate)
    make_stb_exercise,
    make_trace_exercise,
    make_user,
)


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


@pytest.fixture
async def redis() -> Redis:
    client = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def _seed_pool(db_session: AsyncSession) -> None:
    await make_stb_exercise(db_session, concepts=["mutable-default-arg"], difficulty_authored=3)
    await make_trace_exercise(db_session, concepts=["off-by-one"], difficulty_authored=5)
    await make_stb_exercise(db_session, concepts=["closure-late-binding"], difficulty_authored=4)
    await make_trace_exercise(db_session, concepts=["aliasing-vs-copy"], difficulty_authored=6)
    await make_stb_exercise(db_session, concepts=["shared-class-attribute"], difficulty_authored=2)


@pytest.mark.asyncio
async def test_pulled_exercise_disappears_from_cached_and_new_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
    redis: Redis,
) -> None:
    user = await make_user(db_session)
    await _seed_pool(db_session)

    first = await client.get("/v1/session/today", headers=auth_headers(user))
    assert first.status_code == 200
    served_ids = [e["exercise_id"] for e in first.json()["exercises"]]
    assert served_ids
    bad_id = served_ids[0]

    today = dt.datetime.now(dt.UTC).date()
    cache_key = f"session:{user.id}:{today.isoformat()}"
    assert await redis.get(cache_key) is not None

    bad = await db_session.scalar(select(Exercise).where(Exercise.id == bad_id))
    exercise, purged = await pull_exercise(db_session, redis, bad.id, bad.version)

    assert exercise.status == "pulled"
    assert purged == 1
    # Cache key AND persisted row are gone: the very next fetch resamples.
    assert await redis.get(cache_key) is None
    assert await db_session.get(DailySession, (user.id, today)) is None

    rebuilt = await client.get("/v1/session/today", headers=auth_headers(user))
    assert rebuilt.status_code == 200
    rebuilt_ids = [e["exercise_id"] for e in rebuilt.json()["exercises"]]
    assert rebuilt_ids
    assert bad_id not in rebuilt_ids


@pytest.mark.asyncio
async def test_pull_leaves_unrelated_cached_sessions_alone(
    client: AsyncClient,
    db_session: AsyncSession,
    redis: Redis,
) -> None:
    """Negative space of the purge: a live exercise NOT in a user's session
    being pulled must not blow away that user's session."""
    user = await make_user(db_session)
    await _seed_pool(db_session)

    first = await client.get("/v1/session/today", headers=auth_headers(user))
    assert first.status_code == 200

    # Goes live only after the session was built, so it cannot be in it.
    unserved = await make_stb_exercise(
        db_session,
        concepts=["variable-shadowing"],
        difficulty_authored=5,
    )

    _, purged = await pull_exercise(db_session, redis, unserved.id, unserved.version)

    today = dt.datetime.now(dt.UTC).date()
    assert purged == 0
    assert await redis.get(f"session:{user.id}:{today.isoformat()}") is not None
    assert await db_session.get(DailySession, (user.id, today)) is not None
