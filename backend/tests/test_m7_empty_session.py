"""Empty live pool stays transient (audit FIX 3): a zero-candidate build is
never persisted or cached as a "completed" day. Before this fix, the first
user to open their day against an empty pool got a daily_sessions row with
exercise_list=[] plus a 36h cache of [], and stayed locked into an empty
"done" day even after content was restored.
"""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.main import create_app
from app.models import DailySession
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


@pytest.mark.asyncio
async def test_empty_pool_returns_transient_not_completed_and_recovers(
    client: AsyncClient,
    db_session: AsyncSession,
    redis: Redis,
) -> None:
    user = await make_user(db_session)
    today = dt.datetime.now(dt.UTC).date()
    cache_key = f"session:{user.id}:{today.isoformat()}"

    # Pool is empty: transient "no content yet", NOT a completed day.
    empty = await client.get("/v1/session/today", headers=auth_headers(user))
    assert empty.status_code == 200
    body = empty.json()
    assert body["completed"] is False
    assert body["exercises"] == []

    # Nothing persisted, nothing cached -- the day is not locked shut.
    assert await db_session.get(DailySession, (user.id, today)) is None
    assert await redis.get(cache_key) is None

    # Content is restored: the very next fetch builds a real session.
    await _seed_pool(db_session)
    recovered = await client.get("/v1/session/today", headers=auth_headers(user))
    assert recovered.status_code == 200
    assert len(recovered.json()["exercises"]) >= 3
    assert await redis.get(cache_key) is not None


@pytest.mark.asyncio
async def test_legacy_persisted_empty_session_row_is_healed(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Rows persisted with exercise_list=[] before the guard existed must not
    pin the user to an empty day forever."""
    user = await make_user(db_session)
    today = dt.datetime.now(dt.UTC).date()
    db_session.add(DailySession(user_id=user.id, session_date=today, exercise_list=[]))
    await db_session.commit()
    await _seed_pool(db_session)

    response = await client.get("/v1/session/today", headers=auth_headers(user))

    assert response.status_code == 200
    assert len(response.json()["exercises"]) >= 3
