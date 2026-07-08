from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.models import UserConceptState
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)

_TOLERANCE = dt.timedelta(seconds=10)


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


def _idem() -> str:
    return str(uuid.uuid4())


async def _submit(client: AsyncClient, headers: dict, exercise, *, reason_id: str) -> dict:
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


def _assert_close(actual: dt.datetime, expected: dt.datetime) -> None:
    assert abs(actual - expected) < _TOLERANCE, f"{actual} not close to {expected}"


@pytest.mark.asyncio
async def test_wrong_answer_sets_next_review_in_two_days(
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

    before = dt.datetime.now(dt.UTC)
    body = await _submit(client, headers, exercise, reason_id="b")
    assert body["is_correct"] is False

    row = await db_session.get(UserConceptState, (user.id, "mutable-default-arg"))
    assert row is not None
    assert row.attempts == 1
    assert row.correct == 0
    assert float(row.mastery) == pytest.approx(0.0)
    _assert_close(row.next_review_at, before + dt.timedelta(days=2))


@pytest.mark.asyncio
async def test_first_correct_answer_sets_next_review_in_seven_days(
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

    before = dt.datetime.now(dt.UTC)
    body = await _submit(client, headers, exercise, reason_id="a")
    assert body["is_correct"] is True

    row = await db_session.get(UserConceptState, (user.id, "mutable-default-arg"))
    assert row.attempts == 1
    assert row.correct == 1
    assert float(row.mastery) == pytest.approx(0.3, abs=0.001)
    _assert_close(row.next_review_at, before + dt.timedelta(days=7))


@pytest.mark.asyncio
async def test_right_again_sets_next_review_in_twenty_one_days(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-36: 'right again' = correct at least once before on this concept,
    demonstrated here via two DIFFERENT exercises sharing one concept (a
    single exercise can only be attempted once per session/day).
    """
    user = await make_user(db_session)
    first_exercise = await make_stb_exercise(
        db_session,
        concepts=["mutable-default-arg"],
        correct_reason_id="a",
    )
    second_exercise = await make_stb_exercise(
        db_session,
        concepts=["mutable-default-arg"],
        correct_reason_id="a",
    )
    headers = auth_headers(user)
    await client.get("/v1/session/today", headers=headers)

    await _submit(client, headers, first_exercise, reason_id="a")

    before_second = dt.datetime.now(dt.UTC)
    body = await _submit(client, headers, second_exercise, reason_id="a")
    assert body["is_correct"] is True

    row = await db_session.get(UserConceptState, (user.id, "mutable-default-arg"))
    assert row.attempts == 2
    assert row.correct == 2
    assert float(row.mastery) == pytest.approx(0.51, abs=0.001)
    _assert_close(row.next_review_at, before_second + dt.timedelta(days=21))


@pytest.mark.asyncio
async def test_multi_concept_exercise_updates_every_listed_concept(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(
        db_session,
        concepts=["mutable-default-arg", "aliasing-vs-copy"],
        correct_reason_id="a",
    )
    headers = auth_headers(user)
    await client.get("/v1/session/today", headers=headers)

    await _submit(client, headers, exercise, reason_id="a")

    for concept in ("mutable-default-arg", "aliasing-vs-copy"):
        row = await db_session.get(UserConceptState, (user.id, concept))
        assert row is not None
        assert row.attempts == 1
        assert row.correct == 1
