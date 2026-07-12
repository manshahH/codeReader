"""pull_exercise: the working code path to take a bad live exercise out of
circulation (audit FIX 2). docs/00's #1 kill risk is one wrong answer going
viral; the mitigation is a fast pull that also purges the session caches, or
users keep being served the bad exercise for up to 36h.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exercises.service import pull_exercise
from app.main import create_app
from app.models import Attempt, DailySession, Exercise
from app.sessions.service import purge_sessions_referencing
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401 (autouse fixture, must be imported to activate)
    clean_redis,  # noqa: F401 (autouse fixture, must be imported to activate)
    m4_env,  # noqa: F401 (autouse fixture, must be imported to activate)
    make_stb_exercise,
    make_trace_exercise,
    make_user,
)


def _idem() -> str:
    return str(uuid.uuid4())


def _answer_for(exercise: dict) -> dict:
    if exercise["type"] == "spot_the_bug":
        return {"line": 1, "reason_id": "a"}
    return {"choice_id": "a"}


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


@pytest.mark.asyncio
async def test_pull_keeps_completed_sessions_but_purges_in_progress_ones(
    db_session: AsyncSession,
    redis: Redis,
) -> None:
    """D-102: pulling an exercise must NOT erase a COMPLETED daily_session that
    references it -- doing so silently rewrites the user's history (session
    count, activity heatmap, streak evidence) for a day they already finished.
    A finished session is never served for answering again, so the pull's
    content-swap protects the user from nothing there. Only IN-FLIGHT sessions
    (completed_at IS NULL) must be purged, which still fully preserves D-58's
    real purpose (an unfinished session must never serve pulled content)."""
    finished_user = await make_user(db_session)
    in_progress_user = await make_user(db_session)
    bad = await make_trace_exercise(db_session, concepts=["off-by-one"])

    today = dt.datetime.now(dt.UTC).date()
    slot = [{"slot": 1, "exercise_id": str(bad.id), "version": bad.version, "is_boss": False}]
    db_session.add(
        DailySession(
            user_id=finished_user.id,
            session_date=today,
            exercise_list=slot,
            completed_at=dt.datetime.now(dt.UTC),
        ),
    )
    db_session.add(
        DailySession(
            user_id=in_progress_user.id,
            session_date=today,
            exercise_list=slot,
            completed_at=None,
        ),
    )
    await db_session.flush()
    await db_session.commit()

    finished_key = f"session:{finished_user.id}:{today.isoformat()}"
    in_progress_key = f"session:{in_progress_user.id}:{today.isoformat()}"
    await redis.set(finished_key, "[]")
    await redis.set(in_progress_key, "[]")

    purged = await purge_sessions_referencing(db_session, redis, bad.id)

    # Only the in-flight session is purged.
    assert purged == 1
    # The COMPLETED session survives -- both its row and its cache are intact,
    # so the user's finished day is not erased.
    assert await db_session.get(DailySession, (finished_user.id, today)) is not None
    assert await redis.get(finished_key) is not None
    # The IN-PROGRESS session is still purged (D-58 unchanged) -- row and cache.
    assert await db_session.get(DailySession, (in_progress_user.id, today)) is None
    assert await redis.get(in_progress_key) is None


@pytest.mark.asyncio
async def test_pull_of_an_answered_in_progress_exercise_keeps_attempts_and_resamples_honestly(
    client: AsyncClient,
    db_session: AsyncSession,
    redis: Redis,
) -> None:
    """D-102 follow-up (the raised gap): pulling an exercise the user ALREADY
    ANSWERED inside an IN-PROGRESS session must not lose or double-count their
    attempt. The session is purged and resampled (correct -- an unfinished
    session must never keep serving pulled content), but the attempt rows live
    in `attempts`, keyed by (user, exercise, session_date) with no FK to
    daily_sessions, so the purge cannot touch them. The resample prefers
    not-recently-seen exercises, so it does not re-serve an already-attempted
    one; and even if a thin pool forced it to, the already_attempted guard
    409s a re-submit, so a double count is impossible either way.
    """
    user = await make_user(db_session)
    # A pool rich enough that a resample has fresh exercises to choose and is
    # never forced to re-serve an already-attempted one.
    concepts = [
        "mutable-default-arg", "off-by-one", "closure-late-binding", "aliasing-vs-copy",
        "shared-class-attribute", "variable-shadowing", "exception-swallowing", "is-vs-equality",
    ]
    for i, concept in enumerate(concepts):
        if i % 2 == 0:
            await make_stb_exercise(db_session, concepts=[concept], difficulty_authored=4)
        else:
            await make_trace_exercise(db_session, concepts=[concept], difficulty_authored=5)

    headers = auth_headers(user)
    first = await client.get("/v1/session/today", headers=headers)
    slots = first.json()["exercises"]
    assert len(slots) >= 2, "need a multi-exercise session to answer one then pull it"

    # Answer two exercises in the in-progress session; one will be pulled.
    to_pull, other = slots[0], slots[1]
    for ex in (to_pull, other):
        resp = await client.post(
            "/v1/attempts",
            headers={**headers, "Idempotency-Key": _idem()},
            json={
                "exercise_id": ex["exercise_id"],
                "exercise_version": ex["version"],
                "answer": _answer_for(ex),
                "time_taken_ms": 1000,
            },
        )
        assert resp.status_code == 200

    stats_before = (await client.get("/v1/me/stats", headers=headers)).json()
    assert stats_before["total_attempts"] == 2

    # Pull one of the two answered exercises -> its in-progress session is purged.
    pulled = await db_session.scalar(
        select(Exercise).where(Exercise.id == uuid.UUID(to_pull["exercise_id"])),
    )
    _, purged = await pull_exercise(db_session, redis, pulled.id, pulled.version)
    assert purged == 1

    # BOTH attempts survive the purge -- nothing in the attempts table was touched.
    today = dt.datetime.now(dt.UTC).date()
    surviving = (
        await db_session.execute(
            select(Attempt.exercise_id).where(
                Attempt.user_id == user.id,
                Attempt.session_date == today,
            ),
        )
    ).all()
    surviving_ids = {str(row[0]) for row in surviving}
    assert to_pull["exercise_id"] in surviving_ids
    assert other["exercise_id"] in surviving_ids

    # The resampled session never serves the pulled exercise, and does not
    # re-serve the still-live already-attempted one (recently-seen preference).
    resampled = (await client.get("/v1/session/today", headers=headers)).json()
    resampled_ids = {e["exercise_id"] for e in resampled["exercises"]}
    assert to_pull["exercise_id"] not in resampled_ids
    assert other["exercise_id"] not in resampled_ids
    # Progress is honest: every slot's `attempted` flag equals whether a real
    # attempt exists for it (all fresh here -> not completed, no phantom done).
    for e in resampled["exercises"]:
        assert e["attempted"] == (e["exercise_id"] in surviving_ids)
    assert resampled["completed"] is False

    # No double count: the pull + resample changed neither total_attempts nor
    # (implicitly) the streak, which were credited once at submit time.
    stats_after = (await client.get("/v1/me/stats", headers=headers)).json()
    assert stats_after["total_attempts"] == 2
