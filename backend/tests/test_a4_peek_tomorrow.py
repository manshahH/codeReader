"""A4 "peek at tomorrow" (D-142).

The teaser on GET /session/today: a single concept due in the user's LOCAL day
after today, shown only on the completed state, null when nothing is due
tomorrow. Every gate has a negative test:

- gated on `completed`: an in-progress session carries tomorrow: null;
- empty case: a completed day with nothing due tomorrow shows nothing;
- window is disjoint from "due today": a concept due today is never teased;
- selection is deterministic: weakest mastery wins;
- first_completed_session is a one-time cue, false once a prior day completed.

Sessions are seeded directly and completed over HTTP (the same trick M4/M5/M9
tests use), so no sampler and no time mocking are involved.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezones import local_date_for, local_day_end_utc
from app.main import create_app
from app.models import DailySession, UserConceptState
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


def _walk_keys(node: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        keys.update(node.keys())
        for value in node.values():
            keys |= _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            keys |= _walk_keys(item)
    return keys


def _walk_values(node: object) -> set[str]:
    values: set[str] = set()
    if isinstance(node, dict):
        for value in node.values():
            values |= _walk_values(value)
    elif isinstance(node, list):
        for item in node:
            values |= _walk_values(item)
    else:
        values.add(str(node))
    return values


async def _seed_due_concept(
    db: AsyncSession,
    user,
    concept: str,
    *,
    next_review_at: dt.datetime,
    mastery: str = "0.500",
) -> None:
    db.add(
        UserConceptState(
            user_id=user.id,
            concept=concept,
            mastery=decimal.Decimal(mastery),
            next_review_at=next_review_at,
        ),
    )
    await db.flush()
    await db.commit()


async def _seed_uncompleted_session(db: AsyncSession, user) -> tuple:
    """A today session with one STB slot, NOT yet attempted. `today` is the
    user's LOCAL date, so this works for a non-UTC user too."""
    exercise = await make_stb_exercise(db, concepts=["mutable-default-arg"])
    today = local_date_for(user.timezone)
    db.add(
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
    await db.flush()
    await db.commit()
    return exercise, today


async def _complete_session(client: AsyncClient, exercise, headers: dict[str, str]) -> None:
    """Complete the single-slot session over HTTP (sets completed_at + the
    Attempt row the way the real flow does)."""
    response = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "exercise_id": str(exercise.id),
            "exercise_version": exercise.version,
            "answer": {"line": 1, "reason_id": "a"},
            "time_taken_ms": 500,
        },
    )
    assert response.status_code == 200, response.text


def _tomorrow_noon_utc() -> dt.datetime:
    tomorrow = dt.datetime.now(dt.UTC).date() + dt.timedelta(days=1)
    return dt.datetime.combine(tomorrow, dt.time(12, 0), tzinfo=dt.UTC)


# --- happy path + selection rule -------------------------------------------


@pytest.mark.asyncio
async def test_completed_session_teases_the_weakest_mastery_concept_due_tomorrow(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    exercise, _today = await _seed_uncompleted_session(db_session, user)

    # Two concepts due tomorrow; the weaker-mastery one must win (D-142(3)).
    await _seed_due_concept(
        db_session, user, "sorting-stability-assumption",
        next_review_at=_tomorrow_noon_utc(), mastery="0.700",
    )
    await _seed_due_concept(
        db_session, user, "dict-mutation-during-iteration",
        next_review_at=_tomorrow_noon_utc(), mastery="0.100",
    )

    await _complete_session(client, exercise, headers)

    body = (await client.get("/v1/session/today", headers=headers)).json()
    assert body["completed"] is True
    assert body["tomorrow"] is not None
    assert body["tomorrow"]["concept"] == "dict-mutation-during-iteration"
    # First-ever finished day -> the one-time warm cue is on. A real scheduled
    # concept exists, so this is NOT the fallback path.
    assert body["tomorrow"]["first_completed_session"] is True
    assert body["tomorrow"]["is_fallback"] is False
    # Invariant 1/2: nothing gradey ever appears under the teaser.
    assert _walk_keys(body["tomorrow"]).isdisjoint(
        {"grading", "explanation", "reveal", "correct_lines", "correct_reason_id"},
    )


# --- gated on completed (negative) -----------------------------------------


@pytest.mark.asyncio
async def test_in_progress_session_never_teases_tomorrow(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A concept is due tomorrow, but the session is not finished, so the field
    must be null: the teaser ships on the completed state only."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _seed_uncompleted_session(db_session, user)
    await _seed_due_concept(
        db_session, user, "dict-mutation-during-iteration",
        next_review_at=_tomorrow_noon_utc(), mastery="0.100",
    )

    body = (await client.get("/v1/session/today", headers=headers)).json()
    assert body["completed"] is False
    assert body["tomorrow"] is None


# --- empty case (negative) -------------------------------------------------


@pytest.mark.asyncio
async def test_completed_session_with_nothing_due_tomorrow_shows_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Concepts due TODAY and the DAY AFTER tomorrow both fall outside the
    window, so a completed day teases nothing rather than a bare count.

    A RETURNING user (a prior completed day exists), so the first-completed
    fallback (Addendum 5) does not apply -- this is the pure steady-state empty
    case, which stays silent."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _seed_prior_completed_day(db_session, user)
    exercise, _today = await _seed_uncompleted_session(db_session, user)

    now = dt.datetime.now(dt.UTC)
    today = now.date()
    # Due today: strictly before tomorrow's window start (00:00 tomorrow UTC).
    await _seed_due_concept(
        db_session, user, "due-today-not-tomorrow",
        next_review_at=dt.datetime.combine(today, dt.time(9, 0), tzinfo=dt.UTC),
    )
    # Due the day after tomorrow: at/after the window end.
    day_after = today + dt.timedelta(days=2)
    await _seed_due_concept(
        db_session, user, "due-day-after-tomorrow",
        next_review_at=dt.datetime.combine(day_after, dt.time(9, 0), tzinfo=dt.UTC),
    )

    await _complete_session(client, exercise, headers)

    body = (await client.get("/v1/session/today", headers=headers)).json()
    assert body["completed"] is True
    assert body["tomorrow"] is None


# --- first_completed_session cue (negative on the warm variant) ------------


@pytest.mark.asyncio
async def test_first_completed_session_is_false_once_a_prior_day_completed(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)
    # A prior completed day already exists.
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

    exercise, _today = await _seed_uncompleted_session(db_session, user)
    await _seed_due_concept(
        db_session, user, "dict-mutation-during-iteration",
        next_review_at=_tomorrow_noon_utc(), mastery="0.100",
    )

    await _complete_session(client, exercise, headers)

    body = (await client.get("/v1/session/today", headers=headers)).json()
    assert body["tomorrow"] is not None
    assert body["tomorrow"]["concept"] == "dict-mutation-during-iteration"
    # Second finished day -> the warm cue is off, but the teaser still shows.
    assert body["tomorrow"]["first_completed_session"] is False


# --- invariant 1/2: the whole wire body, teaser populated (BLOCKER 1.4) -----


@pytest.mark.asyncio
async def test_completed_teaser_body_leaks_no_grading_explanation_or_exercise_id(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The m4/m5 leak tests walk an IN-PROGRESS body, where `tomorrow` is null.
    This walks the WHOLE completed body with the teaser POPULATED and the
    rendered exercise present, and asserts the A4 field adds no answer-key
    surface: no grading/explanation key anywhere, and the teaser exposes no
    exercise id under any code path (only a concept string + a bool)."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    exercise, _today = await _seed_uncompleted_session(db_session, user)
    await _seed_due_concept(
        db_session, user, "dict-mutation-during-iteration",
        next_review_at=_tomorrow_noon_utc(), mastery="0.100",
    )

    await _complete_session(client, exercise, headers)
    body = (await client.get("/v1/session/today", headers=headers)).json()

    assert body["tomorrow"] is not None  # teaser is actually populated here
    keys = _walk_keys(body)
    assert "grading" not in keys
    assert "explanation" not in keys
    # The teaser is exactly {concept, first_completed_session, is_fallback} --
    # no id leaks.
    assert set(body["tomorrow"].keys()) == {"concept", "first_completed_session", "is_fallback"}
    assert str(exercise.id) not in _walk_values(body["tomorrow"])


# --- local-day boundary, non-UTC timezone (non-blocking 4) ------------------


@pytest.mark.asyncio
async def test_window_uses_local_midnight_not_utc_boundary(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A concept whose next_review_at is exactly the start of the user's LOCAL
    tomorrow renders; the window is computed in the user's timezone, not UTC.
    Asia/Kolkata (UTC+5:30) makes the two boundaries provably different."""
    tz = "Asia/Kolkata"
    user = await make_user(db_session, timezone=tz)
    headers = auth_headers(user)
    exercise, today = await _seed_uncompleted_session(db_session, user)

    local_tomorrow_start = local_day_end_utc(tz, today)  # 18:30 UTC the prior day
    # Proof the boundary is timezone-based: UTC midnight of the same local date
    # is a different instant entirely.
    utc_midnight_tomorrow = dt.datetime.combine(
        today + dt.timedelta(days=1), dt.time.min, tzinfo=dt.UTC,
    )
    assert local_tomorrow_start != utc_midnight_tomorrow

    await _seed_due_concept(
        db_session, user, "dict-mutation-during-iteration",
        next_review_at=local_tomorrow_start,  # inclusive lower edge of the window
    )

    await _complete_session(client, exercise, headers)
    body = (await client.get("/v1/session/today", headers=headers)).json()
    assert body["completed"] is True
    assert body["tomorrow"] is not None
    assert body["tomorrow"]["concept"] == "dict-mutation-during-iteration"


@pytest.mark.asyncio
async def test_concept_one_second_before_local_tomorrow_is_due_today_not_teased(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The 23:59:59-local case: a concept one second before the local day
    boundary is still TODAY, so the strictly-tomorrow window excludes it and
    the teaser is null. This is the edge jobs/streak_recon.py exists for, and
    D-116/D-137's 'a timezone change must not move a recomputation' shape."""
    tz = "Asia/Kolkata"
    user = await make_user(db_session, timezone=tz)
    headers = auth_headers(user)
    # Returning user, so the first-completed fallback (Addendum 5) does not fire
    # and an empty strict window is the pure "nothing tomorrow" case.
    await _seed_prior_completed_day(db_session, user)
    exercise, today = await _seed_uncompleted_session(db_session, user)

    just_before_tomorrow = local_day_end_utc(tz, today) - dt.timedelta(seconds=1)
    await _seed_due_concept(
        db_session, user, "still-due-today",
        next_review_at=just_before_tomorrow,
    )

    await _complete_session(client, exercise, headers)
    body = (await client.get("/v1/session/today", headers=headers)).json()
    assert body["completed"] is True
    assert body["tomorrow"] is None


# --- first-completed-session fallback (D-142 Addendum 5) --------------------


async def _seed_prior_completed_day(db: AsyncSession, user) -> None:
    db.add(
        DailySession(
            user_id=user.id,
            session_date=local_date_for(user.timezone) - dt.timedelta(days=1),
            exercise_list=[],
            completed_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1),
        ),
    )
    await db.flush()
    await db.commit()


@pytest.mark.asyncio
async def test_first_completed_empty_window_falls_back_to_weakest_mastery(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """First-ever completed day + nothing due tomorrow -> render the warm
    fallback on the weakest-mastery concept, flagged is_fallback (no date
    claim). This rescues the day-1 impression that would otherwise render
    nothing (0-52% by the sim)."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    exercise, _today = await _seed_uncompleted_session(db_session, user)
    # A weakest-mastery concept that is NOT due tomorrow (due today), so the
    # strict window is empty but a fallback exists.
    await _seed_due_concept(
        db_session, user, "weakest-overall", mastery="0.000",
        next_review_at=dt.datetime.now(dt.UTC),
    )

    await _complete_session(client, exercise, headers)
    body = (await client.get("/v1/session/today", headers=headers)).json()

    assert body["completed"] is True
    assert body["tomorrow"] is not None
    assert body["tomorrow"]["concept"] == "weakest-overall"
    assert body["tomorrow"]["first_completed_session"] is True
    assert body["tomorrow"]["is_fallback"] is True


@pytest.mark.asyncio
async def test_not_first_completed_empty_window_still_shows_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The fallback is first-completed-ONLY. A returning user with an empty
    window sees nothing, exactly as before -- the fallback must not leak into
    steady state."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    await _seed_prior_completed_day(db_session, user)
    exercise, _today = await _seed_uncompleted_session(db_session, user)
    await _seed_due_concept(
        db_session, user, "weakest-overall", mastery="0.000",
        next_review_at=dt.datetime.now(dt.UTC),
    )

    await _complete_session(client, exercise, headers)
    body = (await client.get("/v1/session/today", headers=headers)).json()

    assert body["completed"] is True
    assert body["tomorrow"] is None


@pytest.mark.asyncio
async def test_first_completed_nonempty_window_uses_scheduled_not_fallback(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """When a real concept IS due tomorrow, the first-completed user gets the
    scheduled concept (with the date claim), never the fallback -- even if a
    weaker-mastery concept exists outside the window."""
    user = await make_user(db_session)
    headers = auth_headers(user)
    exercise, _today = await _seed_uncompleted_session(db_session, user)
    # In-window concept (mastery 0.5) and a WEAKER out-of-window concept (0.1).
    await _seed_due_concept(
        db_session, user, "scheduled-tomorrow", mastery="0.500",
        next_review_at=_tomorrow_noon_utc(),
    )
    await _seed_due_concept(
        db_session, user, "weaker-but-due-today", mastery="0.100",
        next_review_at=dt.datetime.now(dt.UTC),
    )

    await _complete_session(client, exercise, headers)
    body = (await client.get("/v1/session/today", headers=headers)).json()

    assert body["tomorrow"] is not None
    assert body["tomorrow"]["concept"] == "scheduled-tomorrow"
    assert body["tomorrow"]["first_completed_session"] is True
    assert body["tomorrow"]["is_fallback"] is False
