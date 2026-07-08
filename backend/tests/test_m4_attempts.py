from __future__ import annotations

import decimal
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.main import create_app
from app.models import Attempt, ExerciseStat
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


async def _prime_session(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.get("/v1/session/today", headers=headers)
    assert response.status_code == 200
    return response.json()


def _idem() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_spot_the_bug_correct_answer_grades_true_with_reveal(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(
        db_session,
        concepts=["mutable-default-arg"],
        correct_line=1,
        correct_reason_id="a",
    )
    headers = auth_headers(user)
    await _prime_session(client, headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 4200,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["status"] == "graded"
    assert body["reveal"]["correct_lines"] == [1]
    assert body["reveal"]["correct_reason_id"] == "a"
    assert body["reveal"]["explanation"]["summary"]
    assert body["reveal"]["explanation"]["line_notes"]
    # Internal pipeline artifacts must never reach the client, even post-grade.
    assert "verified" not in body["reveal"]["explanation"]
    assert "artifacts" not in body["reveal"]
    assert "mismatch_flagged" not in body["reveal"]["explanation"]
    assert body["session"]["remaining"] == 0
    assert body["session"]["completed"] is True


@pytest.mark.asyncio
async def test_spot_the_bug_incorrect_answer_grades_false(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(
        db_session,
        concepts=["mutable-default-arg"],
        correct_line=1,
        correct_reason_id="a",
    )
    headers = auth_headers(user)
    await _prime_session(client, headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "b"},
            "time_taken_ms": 1000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is False
    # Reveal still shows the correct answer even when the submission was wrong.
    assert body["reveal"]["correct_reason_id"] == "a"


@pytest.mark.asyncio
async def test_trace_correct_answer_grades_true_with_reveal(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_trace_exercise(
        db_session,
        concepts=["off-by-one"],
        correct_choice_id="a",
    )
    headers = auth_headers(user)
    await _prime_session(client, headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"choice_id": "a"},
            "time_taken_ms": 2500,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["reveal"]["correct_choice_id"] == "a"
    assert body["reveal"]["explanation"]["trace_table"]
    assert body["reveal"]["explanation"]["why_wrong"]


@pytest.mark.asyncio
async def test_idempotent_replay_returns_byte_identical_body(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)
    key = _idem()
    request_body = {
        "exercise_id": str(exercise.id),
        "exercise_version": exercise.version,
        "answer": {"line": 1, "reason_id": "a"},
        "time_taken_ms": 3000,
    }

    idem_headers = {**headers, "Idempotency-Key": key}
    first = await client.post("/v1/attempts", headers=idem_headers, json=request_body)
    second = await client.post("/v1/attempts", headers=idem_headers, json=request_body)

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert "X-Idempotent-Replay" not in first.headers
    assert second.headers["X-Idempotent-Replay"] == "true"

    rows = (
        await db_session.scalars(
            select(Attempt).where(Attempt.user_id == user.id, Attempt.exercise_id == exercise.id),
        )
    ).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_idempotency_conflict_same_key_different_body(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)
    key = _idem()

    first = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": key},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        },
    )
    assert first.status_code == 200

    conflict = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": key},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "b"},
            "time_taken_ms": 1000,
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_attempt_on_exercise_not_in_session_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    in_pool = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)  # persists today's session with only `in_pool`

    late_arrival = await make_stb_exercise(db_session, concepts=["off-by-one"])

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(late_arrival.id),
            "exercise_version": late_arrival.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "exercise_not_in_session"
    assert in_pool  # keep reference alive / documents why the session isn't empty


@pytest.mark.asyncio
async def test_second_attempt_same_exercise_returns_409_already_attempted(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    first = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        },
    )
    assert first.status_code == 200

    second = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},  # different key, same exercise
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "b"},
            "time_taken_ms": 1000,
        },
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "already_attempted"


@pytest.mark.asyncio
async def test_answer_shape_mismatch_returns_422(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"choice_id": "a"},  # trace-shaped answer for a spot_the_bug exercise
            "time_taken_ms": 1000,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "answer_shape_mismatch"


@pytest.mark.asyncio
async def test_missing_idempotency_key_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    response = await client.post(
        "/v1/attempts",
        headers=headers,
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_percentile_hidden_below_30_and_shown_at_30(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    below_threshold = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    at_threshold = await make_stb_exercise(db_session, concepts=["off-by-one"])
    headers = auth_headers(user)
    await _prime_session(client, headers)

    db_session.add(
        ExerciseStat(
            exercise_id=below_threshold.id,
            exercise_version=below_threshold.version,
            attempts_count=29,
            correct_count=20,
            solve_rate=decimal.Decimal("0.690"),
        ),
    )
    db_session.add(
        ExerciseStat(
            exercise_id=at_threshold.id,
            exercise_version=at_threshold.version,
            attempts_count=30,
            correct_count=21,
            solve_rate=decimal.Decimal("0.700"),
        ),
    )
    await db_session.flush()
    await db_session.commit()

    below_response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(below_threshold.id),
            "exercise_version": below_threshold.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        },
    )
    at_response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(at_threshold.id),
            "exercise_version": at_threshold.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        },
    )

    assert below_response.json()["percentile"] is None
    at_body = at_response.json()
    assert at_body["percentile"] == {"solve_rate": 0.7, "n": 30}


@pytest.mark.asyncio
async def test_get_attempt_by_id_own_attempts_only(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await make_user(db_session)
    stranger = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    owner_headers = auth_headers(owner)
    await _prime_session(client, owner_headers)

    submit = await client.post(
        "/v1/attempts",
        headers={**owner_headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 1000,
        },
    )
    attempt_id = submit.json()["attempt_id"]

    own_lookup = await client.get(f"/v1/attempts/{attempt_id}", headers=owner_headers)
    assert own_lookup.status_code == 200
    assert own_lookup.json()["attempt_id"] == attempt_id

    stranger_lookup = await client.get(f"/v1/attempts/{attempt_id}", headers=auth_headers(stranger))
    assert stranger_lookup.status_code == 404


@pytest.mark.asyncio
async def test_attempts_rate_limit_returns_429(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_ATTEMPTS_PER_MINUTE", "1")
    get_settings.cache_clear()

    user = await make_user(db_session)
    ex1 = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    ex2 = await make_stb_exercise(db_session, concepts=["off-by-one"])
    headers = auth_headers(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as limited_client:
        await limited_client.get("/v1/session/today", headers=headers)
        first = await limited_client.post(
            "/v1/attempts",
            headers={**headers, "Idempotency-Key": _idem()},
            json={
                "exercise_id": str(ex1.id),
                "exercise_version": ex1.version,
                "answer": {"line": 1, "reason_id": "a"},
                "time_taken_ms": 1000,
            },
        )
        second = await limited_client.post(
            "/v1/attempts",
            headers={**headers, "Idempotency-Key": _idem()},
            json={
                "exercise_id": str(ex2.id),
                "exercise_version": ex2.version,
                "answer": {"line": 1, "reason_id": "a"},
                "time_taken_ms": 1000,
            },
        )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"
    get_settings.cache_clear()
