"""D-93: the "I don't know" contract -- validate_answer_shape/grade_deterministic
accept {"skipped": true} for spot_the_bug/trace/predict_the_fix, and
update_concept_state's third "skipped" branch schedules sooner and decays
less than a wrong answer without inflating the accuracy denominator.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.attempts.grading import (
    AnswerShapeError,
    grade_deterministic,
    is_skip_answer,
    validate_answer_shape,
)
from app.main import create_app
from app.models import Exercise, UserConceptState
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
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


def _idem() -> str:
    return str(uuid.uuid4())


# --- unit: is_skip_answer / validate_answer_shape / grade_deterministic -----


def test_is_skip_answer_requires_the_exact_shape() -> None:
    assert is_skip_answer({"skipped": True}) is True
    assert is_skip_answer({"skipped": False}) is False
    assert is_skip_answer({}) is False
    assert is_skip_answer({"skipped": True, "line": 1}) is False


@pytest.mark.parametrize("exercise_type", ["spot_the_bug", "trace", "predict_the_fix"])
def test_validate_answer_shape_accepts_skip_for_every_deterministic_type(
    exercise_type: str,
) -> None:
    validate_answer_shape(exercise_type, {"skipped": True})  # must not raise


@pytest.mark.parametrize("exercise_type", ["spot_the_bug", "trace", "predict_the_fix"])
def test_validate_answer_shape_still_rejects_malformed_real_answers(exercise_type: str) -> None:
    """The skip branch must be additive, never a relaxation of the existing
    exact-key-set check for a real answer."""
    with pytest.raises(AnswerShapeError):
        validate_answer_shape(exercise_type, {})
    with pytest.raises(AnswerShapeError):
        validate_answer_shape(exercise_type, {"skipped": False})


def test_grade_deterministic_short_circuits_on_skip_without_indexing_answer_keys() -> None:
    exercise = Exercise(
        id=uuid.uuid4(),
        version=1,
        language="python",
        type="spot_the_bug",
        grading_mode="deterministic",
        difficulty_authored=3,
        concepts=["mutable-default-arg"],
        tags=[],
        status="live",
        source={"origin": "test"},
        payload={"code": "x = 1", "context_note": "n"},
        grading={"correct_lines": [1], "correct_reason_id": "a"},
        explanation={"summary": "s", "principle": "p", "line_notes": []},
    )
    # A skip answer carries neither "line" nor "reason_id" -- grade_spot_the_bug
    # would KeyError on either if grade_deterministic didn't short-circuit first.
    assert grade_deterministic(exercise, {"skipped": True}) is None


# --- integration: POST /attempts with a skip -------------------------------


@pytest.mark.asyncio
async def test_skip_spot_the_bug_returns_status_skipped_with_reveal(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await client.get("/v1/session/today", headers=headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"skipped": True},
            "time_taken_ms": 500,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "skipped"
    assert body["is_correct"] is None
    assert body["reveal"] is not None
    assert body["reveal"]["correct_lines"] == [1]


@pytest.mark.asyncio
async def test_skip_trace_returns_status_skipped_with_reveal(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_trace_exercise(db_session, concepts=["list-indexing"])
    headers = auth_headers(user)
    await client.get("/v1/session/today", headers=headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"skipped": True},
            "time_taken_ms": 500,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "skipped"
    assert body["is_correct"] is None
    assert body["reveal"]["correct_choice_id"] == "a"


@pytest.mark.asyncio
async def test_malformed_skip_shape_is_still_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await client.get("/v1/session/today", headers=headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"skipped": False},
            "time_taken_ms": 500,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "answer_shape_mismatch"


@pytest.mark.asyncio
async def test_skip_schedules_concept_sooner_than_wrong_and_does_not_inflate_accuracy(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The one test the build brief calls out by name: a skipped attempt
    schedules the concept sooner than a wrong one, and does not inflate the
    accuracy denominator (user_concept_state.attempts, accuracy_by_type)."""
    wrong_user = await make_user(db_session)
    skip_user = await make_user(db_session)
    wrong_exercise = await make_stb_exercise(
        db_session,
        concepts=["shared-concept"],
        correct_reason_id="a",
    )
    skip_exercise = await make_stb_exercise(
        db_session,
        concepts=["shared-concept"],
        correct_reason_id="a",
    )

    wrong_headers = auth_headers(wrong_user)
    skip_headers = auth_headers(skip_user)
    await client.get("/v1/session/today", headers=wrong_headers)
    await client.get("/v1/session/today", headers=skip_headers)

    wrong_response = await client.post(
        "/v1/attempts",
        headers={**wrong_headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(wrong_exercise.id),
            "exercise_version": wrong_exercise.version,
            "answer": {"line": 1, "reason_id": "b"},  # wrong reason
            "time_taken_ms": 500,
        },
    )
    skip_response = await client.post(
        "/v1/attempts",
        headers={**skip_headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(skip_exercise.id),
            "exercise_version": skip_exercise.version,
            "answer": {"skipped": True},
            "time_taken_ms": 500,
        },
    )
    assert wrong_response.json()["is_correct"] is False
    assert skip_response.json()["status"] == "skipped"

    wrong_row = await db_session.get(UserConceptState, (wrong_user.id, "shared-concept"))
    skip_row = await db_session.get(UserConceptState, (skip_user.id, "shared-concept"))

    # Scheduled sooner: CONCEPT_INTERVAL_SKIPPED_DAYS(1) < CONCEPT_INTERVAL_WRONG_DAYS(2).
    delta = wrong_row.next_review_at - skip_row.next_review_at
    assert dt.timedelta(hours=20) < delta < dt.timedelta(hours=28)

    # Decays less than a wrong answer (both start at mastery=0, so a skip's
    # gentler multiplier keeps it >= the wrong answer's mastery -- here both
    # land at 0 since 0 * anything == 0, so assert via the denominators
    # instead, which is the part that must never be conflated.
    assert wrong_row.attempts == 1
    assert wrong_row.correct == 0
    assert wrong_row.declined == 0
    assert skip_row.attempts == 0
    assert skip_row.correct == 0
    assert skip_row.declined == 1

    wrong_stats = (await client.get("/v1/me/stats", headers=wrong_headers)).json()
    skip_stats = (await client.get("/v1/me/stats", headers=skip_headers)).json()
    assert wrong_stats["accuracy_by_type"] == {"spot_the_bug": 0.0}
    # A skip must never inflate the accuracy denominator: no entry at all,
    # not a 0.0 entry (0.0 would mean "attempted and got it wrong").
    assert skip_stats["accuracy_by_type"] == {}
    # Both still count as a submission toward the day/streak (D-19).
    assert wrong_stats["total_attempts"] == 1
    assert skip_stats["total_attempts"] == 1


@pytest.mark.asyncio
async def test_get_attempt_after_skip_still_returns_the_reveal(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await client.get("/v1/session/today", headers=headers)
    submit = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"skipped": True},
            "time_taken_ms": 500,
        },
    )
    attempt_id = submit.json()["attempt_id"]

    response = await client.get(f"/v1/attempts/{attempt_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "skipped"
    assert body["reveal"] is not None
