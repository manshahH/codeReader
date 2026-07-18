"""D-122: first-of-day session creation is serialized by a per-(user, day) lock.

The bug this proves fixed (root-caused under D-119): two concurrent
GET /v1/session/today for a user with no daily_sessions row both found nothing,
both sampled, and both INSERTed. The loser hit the daily_sessions_pkey unique
violation, and the IntegrityError recovery that exists for exactly this case
then failed on its own re-read (MissingGreenlet from the pool pre-ping), so the
request returned 500. Because that 500 escaped as an unhandled ASGI exception it
carried no CORS headers, so the browser saw a network failure rather than a 500
(see D-121 for that half).

THIS TEST FAILS WITHOUT THE LOCK. Verified by reverting the
pg_advisory_xact_lock in sessions/service.py::_build_and_persist_session and
re-running: one request 500s and the exercise sets differ. It is the same
discipline as the D-104 attempts lock and the A1 repair lock -- a concurrency
guard that cannot be shown to fail without its guard is not evidence of
anything.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import create_engine, create_session_factory
from app.main import create_app
from app.models import DailySession
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)


async def _daily_session_count(user_id: object) -> int:
    engine = create_engine()
    factory = create_session_factory(engine)
    async with factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(DailySession).where(DailySession.user_id == user_id),
        )
    await engine.dispose()
    return int(count or 0)


@pytest.mark.asyncio
async def test_concurrent_first_of_day_session_requests_build_exactly_one_session(
    db_session: AsyncSession,
) -> None:
    """Two REAL concurrent requests, as the user's first session fetch ever.

    asyncio.gather fires both against the ASGI app, so each gets its own DB
    session and connection -- the same shape as the D-104 concurrency tests.
    """
    user = await make_user(db_session)
    for concept in ("mutable-default-arg", "off-by-one", "aliasing"):
        await make_stb_exercise(db_session, concepts=[concept])
    headers = auth_headers(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        first, second = await asyncio.gather(
            client.get("/v1/session/today", headers=headers),
            client.get("/v1/session/today", headers=headers),
        )

    # Both succeed. Before the lock, the loser returned 500 (an unhandled
    # MissingGreenlet out of the IntegrityError recovery).
    assert [first.status_code, second.status_code] == [200, 200], (
        f"expected two 200s, got {first.status_code} and {second.status_code}: "
        f"{first.text[:300]} | {second.text[:300]}"
    )

    # Exactly one row. The PK makes two rows impossible, so the real assertion
    # here is that we got a row at all and neither request errored out.
    assert await _daily_session_count(user.id) == 1

    # Identical sessions. This is the assertion that would catch a "fix" that
    # merely swallowed the conflict and let each caller keep its own sample:
    # two independently sampled sets would differ, and the user would see a
    # different session depending on which response their tab rendered.
    def ids(response: object) -> list[str]:
        return [e["exercise_id"] for e in response.json()["exercises"]]

    assert ids(first) == ids(second)
    assert ids(first), "the session must not be empty"


@pytest.mark.asyncio
async def test_five_concurrent_first_of_day_requests_still_build_one_session(
    db_session: AsyncSession,
) -> None:
    """Negative-pressure version: two requests can pass by luck, five will not.

    Widens the window the lock has to cover, so a lock that only narrows the
    race (rather than closing it) shows up here.
    """
    user = await make_user(db_session)
    for concept in ("mutable-default-arg", "off-by-one", "aliasing"):
        await make_stb_exercise(db_session, concepts=[concept])
    headers = auth_headers(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        responses = await asyncio.gather(
            *(client.get("/v1/session/today", headers=headers) for _ in range(5)),
        )

    assert [r.status_code for r in responses] == [200] * 5, (
        f"every concurrent first-of-day request must succeed: {[r.status_code for r in responses]}"
    )
    assert await _daily_session_count(user.id) == 1

    id_sets = [[e["exercise_id"] for e in r.json()["exercises"]] for r in responses]
    assert all(s == id_sets[0] for s in id_sets), "all callers must see the SAME session"
    assert id_sets[0], "the session must not be empty"
