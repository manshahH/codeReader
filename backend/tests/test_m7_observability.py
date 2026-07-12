"""M7 observability: GET /admin/metrics (session-fetch p95, attempt-insert
error rate, pending-grade count, per-exercise dispute rate) and the
baseline security response headers.
"""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.main import create_app
from app.models import Attempt, Dispute, ExerciseStat
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)


@pytest.fixture(autouse=True)
def admin_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_METRICS_TOKEN", "test-admin-metrics-token")
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_admin_metrics_requires_token_and_reports_golden_signals(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)

    db_session.add(
        Attempt(
            user_id=user.id,
            exercise_id=exercise.id,
            exercise_version=exercise.version,
            session_date=dt.date(2026, 7, 1),
            answer={"text": "pending"},
            grading_mode="rubric",
            status="grading_pending",
            time_taken_ms=1000,
        ),
    )
    db_session.add(
        ExerciseStat(
            exercise_id=exercise.id,
            exercise_version=exercise.version,
            attempts_count=10,
            correct_count=6,
            solve_rate=0.6,
        ),
    )
    db_session.add(
        Dispute(
            exercise_id=exercise.id,
            exercise_version=exercise.version,
            user_id=user.id,
            reason="wrong_answer",
            body="the fix is wrong",
            status="open",
        ),
    )
    await db_session.commit()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        await client.get("/v1/session/today", headers=headers)

        no_token = await client.get("/admin/metrics")
        wrong_token = await client.get("/admin/metrics", headers={"X-Admin-Token": "nope"})
        ok = await client.get(
            "/admin/metrics",
            headers={"X-Admin-Token": "test-admin-metrics-token"},
        )

    assert no_token.status_code == 403
    assert wrong_token.status_code == 403
    assert ok.status_code == 200

    body = ok.json()
    assert body["pending_grade_count"] >= 1
    assert body["session_fetch_p95_ms"] is not None
    assert body["attempt_insert_error_rate"]["total"] == 0

    dispute_rows = {row["exercise_id"]: row for row in body["dispute_rate_by_exercise"]}
    row = dispute_rows[str(exercise.id)]
    assert row["open_disputes"] == 1
    assert row["graded_attempts"] == 10
    assert row["dispute_rate"] == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_admin_metrics_disabled_returns_404_when_no_token_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_METRICS_TOKEN", "")
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        response = await client.get("/admin/metrics", headers={"X-Admin-Token": "anything"})

    get_settings.cache_clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_baseline_security_headers_present_on_every_response() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        response = await client.get("/healthz")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers
    # Non-production by default in tests: HSTS must NOT be sent over plain
    # http local dev.
    assert "Strict-Transport-Security" not in response.headers


@pytest.mark.asyncio
async def test_hsts_header_present_only_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "production")
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        response = await client.get("/healthz")

    get_settings.cache_clear()
    expected = "max-age=63072000; includeSubDomains; preload"
    assert response.headers["Strict-Transport-Security"] == expected
