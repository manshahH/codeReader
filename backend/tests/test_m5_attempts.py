"""M5: summarize dispatch through POST /attempts and GET /attempts/{id}.

grade_rubric() itself (injection hardening, scoring, retry-once-then-fail,
timeout) is proven in test_m5_rubric.py without any HTTP/DB layer. These
tests prove the wiring around it: the pending/failed/graded status
transitions, D-19 (streak counts on a pending grade), D-38 (session progress
counts a submitted-but-pending attempt), and that grading_failed is a
terminal, graceful response -- never a 500 or a hang.
"""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.attempts.grader_client import ScriptedGraderClient
from app.config import get_settings
from app.jobs.grading_retry import resolve_pending_summarize_grades
from app.main import create_app
from tests.factories_m4 import (
    SUMMARIZE_MUST_MENTION,
    SUMMARIZE_REFERENCE_ANSWER,
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_summarize_exercise,
    make_user,
)


@pytest.fixture(autouse=True)
def _enable_summarize(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-123: summarize is OFF by default now, and these tests are ABOUT
    summarize, so they opt in explicitly. Without this they would be asserting
    behaviour the shipped configuration deliberately does not have."""
    monkeypatch.setenv("SUMMARIZE_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


def _idem() -> str:
    return str(uuid.uuid4())


def _grader_json(hits: list[str], violations: list[str] | None = None) -> str:
    return json.dumps(
        {"must_mention_hits": hits, "must_not_claim_violations": violations or []},
    )


def _patch_grader(monkeypatch: pytest.MonkeyPatch, scripted: ScriptedGraderClient) -> None:
    monkeypatch.setattr(
        "app.attempts.rubric.get_default_grader_client",
        lambda model: scripted,
    )


async def _prime_session(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.get("/v1/session/today", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_good_summarize_answer_grades_correct_with_reveal_shape(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await make_user(db_session)
    exercise = await make_summarize_exercise(db_session, concepts=["retry-without-backoff"])
    scripted = ScriptedGraderClient(
        [_grader_json(hits=[item["point"] for item in SUMMARIZE_MUST_MENTION])],
    )
    _patch_grader(monkeypatch, scripted)
    headers = auth_headers(user)
    await _prime_session(client, headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {
                "text": "Retries the call with exponential backoff, only for "
                "network errors, and re-raises after the final attempt.",
            },
            "time_taken_ms": 12000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "graded"
    assert body["is_correct"] is True
    assert body["score"] == pytest.approx(1.0)
    assert body["grader_output"]["rubric_hits"]
    assert body["grader_output"]["reference_answer"] == SUMMARIZE_REFERENCE_ANSWER
    assert body["reveal"]["explanation"]["summary"]
    # No deterministic-only fields leak into a summarize reveal.
    assert "correct_lines" not in body["reveal"]
    assert "correct_choice_id" not in body["reveal"]
    assert body["session"]["completed"] is True
    assert len(scripted.calls) == 1


@pytest.mark.asyncio
async def test_summarize_answer_shape_422_over_max_words(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    exercise = await make_summarize_exercise(
        db_session,
        concepts=["retry-without-backoff"],
        max_words=5,
    )
    headers = auth_headers(user)
    await _prime_session(client, headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"text": "This answer has way more than five words in it."},
            "time_taken_ms": 5000,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "answer_shape_mismatch"


@pytest.mark.asyncio
async def test_invalid_grader_json_retried_once_then_grading_failed(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await make_user(db_session)
    exercise = await make_summarize_exercise(db_session, concepts=["retry-without-backoff"])
    scripted = ScriptedGraderClient(["not json at all", '{"wrong_key": []}'])
    _patch_grader(monkeypatch, scripted)
    headers = auth_headers(user)
    await _prime_session(client, headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"text": "Retries with backoff, scoped to network errors."},
            "time_taken_ms": 8000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "grading_failed"
    assert body["is_correct"] is None
    assert body["reveal"] is None
    assert len(scripted.calls) == 2

    attempt_id = body["attempt_id"]

    # Terminal + graceful: GET /attempts/{id} reports it plainly, never a 500.
    get_response = await client.get(f"/v1/attempts/{attempt_id}", headers=headers)
    assert get_response.status_code == 200
    get_body = get_response.json()
    assert get_body["status"] == "grading_failed"
    assert get_body["reveal"] is None
    assert get_body["is_correct"] is None

    # The retry job only ever scans grading_pending -- a grading_failed row
    # is never re-picked, so a second run touches nothing.
    result = await resolve_pending_summarize_grades(db_session)
    assert result == {"resolved": 0, "failed": 0, "still_pending": 0}


@pytest.mark.asyncio
async def test_timeout_then_pending_then_retry_job_resolves_to_graded(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await make_user(db_session)
    exercise = await make_summarize_exercise(db_session, concepts=["retry-without-backoff"])
    failing_client = ScriptedGraderClient([ConnectionError("boom")])
    _patch_grader(monkeypatch, failing_client)
    headers = auth_headers(user)
    await _prime_session(client, headers)

    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": _idem()},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"text": "Retries with backoff, scoped to network errors."},
            "time_taken_ms": 9000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "grading_pending"
    assert body["is_correct"] is None
    assert body["reveal"] is None
    # D-19: streak counts, and session progress counts the submission, even
    # though grading hasn't resolved yet (D-38).
    assert body["streak"] == {"current": 1, "event": "extended"}
    assert body["session"]["completed"] is True

    attempt_id = body["attempt_id"]
    get_pending = await client.get(f"/v1/attempts/{attempt_id}", headers=headers)
    assert get_pending.status_code == 200
    assert get_pending.headers["Retry-After"] == "3"
    assert get_pending.json()["status"] == "grading_pending"

    succeeding_client = ScriptedGraderClient(
        [_grader_json(hits=[item["point"] for item in SUMMARIZE_MUST_MENTION])],
    )
    _patch_grader(monkeypatch, succeeding_client)

    result = await resolve_pending_summarize_grades(db_session)
    assert result == {"resolved": 1, "failed": 0, "still_pending": 0}

    get_resolved = await client.get(f"/v1/attempts/{attempt_id}", headers=headers)
    assert get_resolved.status_code == 200
    resolved_body = get_resolved.json()
    assert resolved_body["status"] == "graded"
    assert resolved_body["is_correct"] is True
    assert resolved_body["reveal"]["explanation"]["summary"]
    assert "Retry-After" not in get_resolved.headers
