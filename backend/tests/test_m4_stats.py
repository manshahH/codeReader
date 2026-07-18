from __future__ import annotations

import datetime as dt
import decimal
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.percentiles import compute_exercise_stats
from app.main import create_app
from app.models import Attempt, ExerciseStat, UserConceptState
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


def _idem() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_me_stats_defaults_to_zero_with_no_attempts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)

    response = await client.get("/v1/me/stats", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {
        "current_streak": 0,
        "longest_streak": 0,
        "streak_freezes": 0,
        "total_attempts": 0,
        "total_correct": 0,
        "accuracy_by_type": {},
        "last_active_local_date": None,
        "total_sessions": 0,
        # A1: no stats row means no reset ever happened, so nothing to restore.
        "repair_available": False,
        "repair_restores_to": None,
    }


@pytest.mark.asyncio
async def test_me_stats_reflects_precomputed_user_stats_after_an_attempt(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(
        db_session,
        concepts=["mutable-default-arg"],
        correct_reason_id="a",
    )
    headers = auth_headers(user)
    await client.get("/v1/session/today", headers=headers)
    await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        },
    )

    response = await client.get("/v1/me/stats", headers=headers)

    body = response.json()
    assert body["total_attempts"] == 1
    assert body["total_correct"] == 1
    assert body["current_streak"] == 1
    assert body["accuracy_by_type"] == {"spot_the_bug": 1.0}


@pytest.mark.asyncio
async def test_me_concepts_sorted_weakest_mastery_first(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    db_session.add_all(
        [
            UserConceptState(
                user_id=user.id,
                concept="strong-concept",
                mastery=decimal.Decimal("0.900"),
            ),
            UserConceptState(
                user_id=user.id,
                concept="weak-concept",
                mastery=decimal.Decimal("0.100"),
            ),
            UserConceptState(
                user_id=user.id,
                concept="mid-concept",
                mastery=decimal.Decimal("0.500"),
            ),
        ],
    )
    await db_session.flush()
    await db_session.commit()

    response = await client.get("/v1/me/concepts", headers=auth_headers(user))

    body = response.json()
    assert [c["concept"] for c in body] == ["weak-concept", "mid-concept", "strong-concept"]
    assert body[0]["mastery"] == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_me_stats_and_concepts_never_aggregate_attempts_at_request_time(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /me/stats and /me/concepts must read only the precomputed
    user_stats/user_concept_state tables. Prove it by inserting attempts
    directly (bypassing the attempt service, so user_stats/user_concept_state
    are never touched) and asserting the read endpoints don't reflect them.
    """
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    now = dt.datetime.now(dt.UTC)
    for _ in range(50):
        db_session.add(
            Attempt(
                user_id=user.id,
                exercise_id=exercise.id,
                exercise_version=exercise.version,
                session_date=now.date(),
                answer={"line": 1, "reason_id": "a"},
                grading_mode="deterministic",
                status="graded",
                is_correct=True,
                created_at=now,
                graded_at=now,
            ),
        )
    await db_session.flush()
    await db_session.commit()

    stats = await client.get("/v1/me/stats", headers=auth_headers(user))
    concepts = await client.get("/v1/me/concepts", headers=auth_headers(user))

    assert stats.json()["total_attempts"] == 0
    assert concepts.json() == []


@pytest.mark.asyncio
async def test_compute_exercise_stats_job_aggregates_attempts_into_exercise_stats(
    db_session: AsyncSession,
) -> None:
    # Four DISTINCT users -- docs/05's one-attempt-per-exercise-per-session
    # rule means a single user can never legitimately have more than one
    # graded attempt for the same (exercise, session_date); see the
    # dedup-specific test below for that same-user case.
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    now = dt.datetime.now(dt.UTC)
    outcomes = [True, True, False, True]
    times = [1000, 2000, 3000, 4000]
    for is_correct, time_taken_ms in zip(outcomes, times, strict=True):
        user = await make_user(db_session)
        db_session.add(
            Attempt(
                user_id=user.id,
                exercise_id=exercise.id,
                exercise_version=exercise.version,
                session_date=now.date(),
                answer={"line": 1, "reason_id": "a"},
                grading_mode="deterministic",
                status="graded",
                is_correct=is_correct,
                time_taken_ms=time_taken_ms,
                created_at=now,
                graded_at=now,
            ),
        )
    await db_session.flush()
    await db_session.commit()

    updated = await compute_exercise_stats(db_session)

    assert updated == 1
    stat = await db_session.get(ExerciseStat, (exercise.id, exercise.version))
    assert stat.attempts_count == 4
    assert stat.correct_count == 3
    assert float(stat.solve_rate) == pytest.approx(0.75)
    assert stat.median_time_ms == 2500


@pytest.mark.asyncio
async def test_compute_exercise_stats_dedupes_duplicate_attempt_rows(
    db_session: AsyncSession,
) -> None:
    """D-8 corrected: a replay racing a Redis idempotency-cache loss can
    duplicate an attempts row for the same (user, exercise_id,
    exercise_version, session_date). The percentiles job must collapse
    those to the single EARLIEST row before counting, so a duplicate never
    inflates a percentile's n or skews its solve rate.
    """
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    now = dt.datetime.now(dt.UTC)
    session_date = now.date()

    # The earliest row: correct, 1000ms. A "duplicate" landed 5s later:
    # incorrect, 9000ms -- if dedup didn't work this would double-count and
    # drag the solve rate/median down.
    db_session.add(
        Attempt(
            user_id=user.id,
            exercise_id=exercise.id,
            exercise_version=exercise.version,
            session_date=session_date,
            answer={"line": 1, "reason_id": "a"},
            grading_mode="deterministic",
            status="graded",
            is_correct=True,
            time_taken_ms=1000,
            created_at=now,
            graded_at=now,
        ),
    )
    db_session.add(
        Attempt(
            user_id=user.id,
            exercise_id=exercise.id,
            exercise_version=exercise.version,
            session_date=session_date,
            answer={"line": 1, "reason_id": "a"},
            grading_mode="deterministic",
            status="graded",
            is_correct=False,
            time_taken_ms=9000,
            created_at=now + dt.timedelta(seconds=5),
            graded_at=now + dt.timedelta(seconds=5),
        ),
    )
    await db_session.flush()
    await db_session.commit()

    updated = await compute_exercise_stats(db_session)

    assert updated == 1
    stat = await db_session.get(ExerciseStat, (exercise.id, exercise.version))
    assert stat.attempts_count == 1
    assert stat.correct_count == 1
    assert float(stat.solve_rate) == pytest.approx(1.0)
    assert stat.median_time_ms == 1000
