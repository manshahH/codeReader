"""M9 UX upgrade backend surface (D-94/D-95/D-96/D-97):
GET /me/activity, GET /session/today/review, POST+GET /me/review,
GET /admin/reviews, and session.first_completed_session on POST /attempts.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.main import create_app
from app.models import DailySession
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


async def _complete_one_exercise_session(
    client: AsyncClient,
    db_session: AsyncSession,
    user,
    headers: dict[str, str],
) -> dict:
    """Builds a single-exercise session directly (bypassing the sampler, same
    trick M4/M5 tests use) so completing it is a single POST /attempts call."""
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    today = dt.datetime.now(dt.UTC).date()
    db_session.add(
        DailySession(
            user_id=user.id,
            session_date=today,
            exercise_list=[
                {
                    "slot": 1,
                    "exercise_id": str(exercise.id),
                    "version": exercise.version,
                    "is_boss": False,
                },
            ],
        ),
    )
    await db_session.flush()
    await db_session.commit()

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 500,
        },
    )
    return response.json()


# --- GET /me/activity --------------------------------------------------


@pytest.mark.asyncio
async def test_activity_reflects_daily_sessions_rows_in_range(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    today = dt.datetime.now(dt.UTC).date()
    db_session.add_all(
        [
            DailySession(
                user_id=user.id,
                session_date=today - dt.timedelta(days=1),
                exercise_list=[],
                completed_at=dt.datetime.now(dt.UTC),
            ),
            DailySession(user_id=user.id, session_date=today, exercise_list=[]),
        ],
    )
    await db_session.flush()
    await db_session.commit()

    response = await client.get("/v1/me/activity", headers=auth_headers(user))

    assert response.status_code == 200
    body = {row["session_date"]: row["completed"] for row in response.json()}
    assert body[(today - dt.timedelta(days=1)).isoformat()] is True
    assert body[today.isoformat()] is False


@pytest.mark.asyncio
async def test_activity_defaults_to_a_365_day_window(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    today = dt.datetime.now(dt.UTC).date()
    db_session.add_all(
        [
            DailySession(user_id=user.id, session_date=today, exercise_list=[]),
            DailySession(
                user_id=user.id,
                session_date=today - dt.timedelta(days=400),
                exercise_list=[],
            ),
        ],
    )
    await db_session.flush()
    await db_session.commit()

    response = await client.get("/v1/me/activity", headers=auth_headers(user))

    dates = {row["session_date"] for row in response.json()}
    assert today.isoformat() in dates
    assert (today - dt.timedelta(days=400)).isoformat() not in dates


@pytest.mark.asyncio
async def test_activity_respects_explicit_from_to(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    today = dt.datetime.now(dt.UTC).date()
    db_session.add(DailySession(user_id=user.id, session_date=today, exercise_list=[]))
    await db_session.flush()
    await db_session.commit()

    response = await client.get(
        "/v1/me/activity",
        params={
            "from": (today - dt.timedelta(days=2)).isoformat(),
            "to": (today - dt.timedelta(days=1)).isoformat(),
        },
        headers=auth_headers(user),
    )

    assert response.json() == []


# --- GET /session/today/review ------------------------------------------


@pytest.mark.asyncio
async def test_session_review_includes_only_attempted_exercises_with_reveal(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    attempted = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    unattempted = await make_stb_exercise(db_session, concepts=["other-concept"])
    today = dt.datetime.now(dt.UTC).date()
    db_session.add(
        DailySession(
            user_id=user.id,
            session_date=today,
            exercise_list=[
                {
                    "slot": 1,
                    "exercise_id": str(attempted.id),
                    "version": attempted.version,
                    "is_boss": False,
                },
                {
                    "slot": 2,
                    "exercise_id": str(unattempted.id),
                    "version": unattempted.version,
                    "is_boss": False,
                },
            ],
        ),
    )
    await db_session.flush()
    await db_session.commit()

    await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(attempted.id),
            "exercise_version": attempted.version,
            "answer": {"skipped": True},
            "time_taken_ms": 500,
        },
    )

    response = await client.get("/v1/session/today/review", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["exercises"]) == 1
    reviewed = body["exercises"][0]
    assert reviewed["exercise_id"] == str(attempted.id)
    assert reviewed["verdict"] == "skipped"
    assert reviewed["answer"] == {"skipped": True}
    assert reviewed["reveal"]["correct_lines"] == [1]


@pytest.mark.asyncio
async def test_session_review_empty_when_no_session_yet(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    response = await client.get("/v1/session/today/review", headers=auth_headers(user))
    assert response.status_code == 200
    assert response.json()["exercises"] == []


# --- POST/GET /me/review + GET /admin/reviews ----------------------------


@pytest.mark.asyncio
async def test_review_upsert_replaces_the_prior_review(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)

    first = await client.post("/v1/me/review", headers=headers, json={"rating": 3, "body": "ok"})
    assert first.status_code == 200
    assert first.json()["rating"] == 3

    second = await client.post(
        "/v1/me/review",
        headers=headers,
        json={"rating": 5, "body": "great"},
    )
    assert second.status_code == 200
    assert second.json()["rating"] == 5
    assert second.json()["body"] == "great"

    status = await client.get("/v1/me/review", headers=headers)
    assert status.json() == {"reviewed": True, "review": second.json()}


@pytest.mark.asyncio
async def test_review_status_before_any_review(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    response = await client.get("/v1/me/review", headers=auth_headers(user))
    assert response.json() == {"reviewed": False, "review": None}


@pytest.mark.asyncio
async def test_review_rejects_out_of_range_rating(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    response = await client.post(
        "/v1/me/review",
        headers=auth_headers(user),
        json={"rating": 6},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_reviews_requires_the_shared_secret_token(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_METRICS_TOKEN", "secret-token")
    get_settings.cache_clear()
    user = await make_user(db_session)
    await client.post("/v1/me/review", headers=auth_headers(user), json={"rating": 4})

    denied = await client.get("/admin/reviews")
    assert denied.status_code in (403, 404)

    allowed = await client.get("/admin/reviews", headers={"X-Admin-Token": "secret-token"})
    assert allowed.status_code == 200
    assert len(allowed.json()) == 1
    assert allowed.json()[0]["rating"] == 4
    get_settings.cache_clear()


# --- session.first_completed_session -------------------------------------


@pytest.mark.asyncio
async def test_first_completed_session_true_only_on_the_completing_first_ever_session(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)

    body = await _complete_one_exercise_session(client, db_session, user, headers)

    assert body["session"]["completed"] is True
    assert body["session"]["first_completed_session"] is True


@pytest.mark.asyncio
async def test_first_completed_session_false_when_a_prior_day_was_already_completed(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Seed yesterday's session as already-completed (no time mocking needed
    -- just a prior DailySession row with completed_at set), then complete
    today's session over HTTP. The completed-count is 2 at that point, so
    first_completed_session must be False."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    db_session.add(
        DailySession(
            user_id=user.id,
            session_date=dt.datetime.now(dt.UTC).date() - dt.timedelta(days=1),
            exercise_list=[],
            completed_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1),
        ),
    )
    await db_session.flush()
    await db_session.commit()

    body = await _complete_one_exercise_session(client, db_session, user, headers)

    assert body["session"]["completed"] is True
    assert body["session"]["first_completed_session"] is False


# --- GET /me/sessions ------------------------------------------------------


@pytest.mark.asyncio
async def test_me_sessions_joins_daily_sessions_to_attempts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    correct_exercise = await make_stb_exercise(
        db_session, concepts=["mutable-default-arg"], correct_reason_id="a",
    )
    skipped_exercise = await make_trace_exercise(db_session, concepts=["list-indexing"])
    today = dt.datetime.now(dt.UTC).date()
    db_session.add(
        DailySession(
            user_id=user.id,
            session_date=today,
            exercise_list=[
                {
                    "slot": 1,
                    "exercise_id": str(correct_exercise.id),
                    "version": correct_exercise.version,
                    "is_boss": False,
                },
                {
                    "slot": 2,
                    "exercise_id": str(skipped_exercise.id),
                    "version": skipped_exercise.version,
                    "is_boss": False,
                },
            ],
        ),
    )
    await db_session.flush()
    await db_session.commit()

    await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(correct_exercise.id),
            "exercise_version": correct_exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 500,
        },
    )
    await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(skipped_exercise.id),
            "exercise_version": skipped_exercise.version,
            "answer": {"skipped": True},
            "time_taken_ms": 500,
        },
    )

    response = await client.get("/v1/me/sessions", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    assert row["session_date"] == today.isoformat()
    assert row["completed"] is True
    assert row["exercise_count"] == 2
    assert row["correct_count"] == 1
    assert row["skipped_count"] == 1
    assert row["concepts"] == sorted(["mutable-default-arg", "list-indexing"])


@pytest.mark.asyncio
async def test_me_sessions_respects_limit_and_orders_most_recent_first(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    today = dt.datetime.now(dt.UTC).date()
    db_session.add_all(
        [
            DailySession(user_id=user.id, session_date=today, exercise_list=[]),
            DailySession(
                user_id=user.id, session_date=today - dt.timedelta(days=1), exercise_list=[],
            ),
            DailySession(
                user_id=user.id, session_date=today - dt.timedelta(days=2), exercise_list=[],
            ),
        ],
    )
    await db_session.flush()
    await db_session.commit()

    response = await client.get("/v1/me/sessions?limit=2", headers=auth_headers(user))

    assert response.status_code == 200
    body = response.json()
    assert [row["session_date"] for row in body] == [
        today.isoformat(),
        (today - dt.timedelta(days=1)).isoformat(),
    ]


# --- GET /me/stats: total_sessions -----------------------------------------


@pytest.mark.asyncio
async def test_me_stats_total_sessions_counts_only_completed_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    today = dt.datetime.now(dt.UTC).date()
    db_session.add_all(
        [
            DailySession(
                user_id=user.id,
                session_date=today - dt.timedelta(days=1),
                exercise_list=[],
                completed_at=dt.datetime.now(dt.UTC),
            ),
            DailySession(user_id=user.id, session_date=today, exercise_list=[]),
        ],
    )
    await db_session.flush()
    await db_session.commit()

    response = await client.get("/v1/me/stats", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["total_sessions"] == 1


@pytest.mark.asyncio
async def test_me_stats_total_sessions_zero_for_a_brand_new_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    response = await client.get("/v1/me/stats", headers=auth_headers(user))
    assert response.json()["total_sessions"] == 0


# --- GET /me/accuracy-history ------------------------------------------------


@pytest.mark.asyncio
async def test_accuracy_history_excludes_skips_from_numerator_and_denominator(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    correct_exercise = await make_stb_exercise(
        db_session, concepts=["mutable-default-arg"], correct_reason_id="a",
    )
    wrong_exercise = await make_stb_exercise(
        db_session, concepts=["shared-concept"], correct_reason_id="a",
    )
    skipped_exercise = await make_trace_exercise(db_session, concepts=["list-indexing"])
    today = dt.datetime.now(dt.UTC).date()
    db_session.add(
        DailySession(
            user_id=user.id,
            session_date=today,
            exercise_list=[
                {"slot": 1, "exercise_id": str(correct_exercise.id), "version": correct_exercise.version, "is_boss": False},
                {"slot": 2, "exercise_id": str(wrong_exercise.id), "version": wrong_exercise.version, "is_boss": False},
                {"slot": 3, "exercise_id": str(skipped_exercise.id), "version": skipped_exercise.version, "is_boss": False},
            ],
        ),
    )
    await db_session.flush()
    await db_session.commit()

    await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(correct_exercise.id),
            "exercise_version": correct_exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 500,
        },
    )
    await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(wrong_exercise.id),
            "exercise_version": wrong_exercise.version,
            "answer": {"line": 1, "reason_id": "b"},
            "time_taken_ms": 500,
        },
    )
    await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(skipped_exercise.id),
            "exercise_version": skipped_exercise.version,
            "answer": {"skipped": True},
            "time_taken_ms": 500,
        },
    )

    response = await client.get("/v1/me/accuracy-history", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["date"] == today.isoformat()
    assert body[0]["attempts"] == 2
    assert body[0]["accuracy"] == 0.5


@pytest.mark.asyncio
async def test_accuracy_history_respects_explicit_from_to(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    response = await client.get(
        "/v1/me/accuracy-history",
        params={"from": "2000-01-01", "to": "2000-01-02"},
        headers=auth_headers(user),
    )
    assert response.status_code == 200
    assert response.json() == []
