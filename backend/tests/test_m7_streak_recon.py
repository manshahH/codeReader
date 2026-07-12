"""M7 streak reconciliation: a westward timezone change must never
retroactively break a streak (docs/05 section 3), the gap docs/ops-runbook.md
flagged and the existing M4 streak tests all missed because they hold the
timezone fixed.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezones import local_date_for
from app.jobs.streak_recon import reconcile_streak_for_timezone_change
from app.main import create_app
from app.models import StreakEvent, UserStats
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)

# A ~25 hour swing: Kiritimati sits at the far EAST of the date line
# (UTC+14), Midway at the far WEST (UTC-11). Moving from one to the other
# is the most extreme westward jump the IANA database allows.
EASTMOST_TZ = "Pacific/Kiritimati"
WESTMOST_TZ = "Pacific/Midway"


async def _streak_events(db_session: AsyncSession, user_id: uuid.UUID) -> list[StreakEvent]:
    rows = await db_session.scalars(
        select(StreakEvent).where(StreakEvent.user_id == user_id).order_by(StreakEvent.created_at),
    )
    return list(rows.all())


@pytest.mark.asyncio
async def test_westward_timezone_change_repairs_last_active_date_not_reset(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session, timezone=EASTMOST_TZ)
    today_east = local_date_for(EASTMOST_TZ)
    db_session.add(
        UserStats(
            user_id=user.id,
            current_streak=5,
            longest_streak=5,
            last_active_local_date=today_east,
        ),
    )
    await db_session.flush()
    await db_session.commit()

    today_west = local_date_for(WESTMOST_TZ)
    assert today_west < today_east, "fixture assumption: this swing must move the date backward"

    await reconcile_streak_for_timezone_change(db_session, user, WESTMOST_TZ)
    await db_session.commit()

    stats = await db_session.get(UserStats, user.id)
    assert stats.current_streak == 5, "the streak VALUE must never be touched by a repair"
    assert stats.last_active_local_date == today_west

    events = await _streak_events(db_session, user.id)
    assert len(events) == 1
    assert events[0].event == "repaired"
    assert events[0].from_value == 5
    assert events[0].to_value == 5
    assert events[0].local_date == today_west


@pytest.mark.asyncio
async def test_eastward_timezone_change_does_not_repair(db_session: AsyncSession) -> None:
    user = await make_user(db_session, timezone=WESTMOST_TZ)
    today_west = local_date_for(WESTMOST_TZ)
    db_session.add(
        UserStats(
            user_id=user.id,
            current_streak=3,
            longest_streak=3,
            last_active_local_date=today_west,
        ),
    )
    await db_session.flush()
    await db_session.commit()

    # Moving EAST only ever advances (or holds) the local date -- the
    # existing extend/reset day-math already handles that correctly, so no
    # repair event should fire.
    await reconcile_streak_for_timezone_change(db_session, user, EASTMOST_TZ)
    await db_session.commit()

    stats = await db_session.get(UserStats, user.id)
    assert stats.last_active_local_date == today_west
    assert await _streak_events(db_session, user.id) == []


@pytest.mark.asyncio
async def test_reconcile_is_a_noop_with_no_prior_activity(db_session: AsyncSession) -> None:
    user = await make_user(db_session, timezone=EASTMOST_TZ)
    # No UserStats row at all -- a brand new user changing timezone during
    # onboarding, before ever submitting anything.
    await reconcile_streak_for_timezone_change(db_session, user, WESTMOST_TZ)
    await db_session.commit()
    assert await _streak_events(db_session, user.id) == []


@pytest.mark.asyncio
async def test_patch_me_westward_timezone_change_then_submit_keeps_streak_alive(
    db_session: AsyncSession,
) -> None:
    """End to end through the real endpoints: PATCH /me changes timezone
    westward across an already-counted day, then the user submits again --
    without the fix this next submit's `today` (computed under the new
    timezone) sits BEFORE the recorded last_active_local_date, satisfying
    neither the "already counted" nor "consecutive" branch in
    attempts/service.py, and the streak silently resets to 1.
    """
    user = await make_user(db_session, timezone=EASTMOST_TZ)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)

    today_east = local_date_for(EASTMOST_TZ)
    db_session.add(
        UserStats(
            user_id=user.id,
            current_streak=5,
            longest_streak=5,
            last_active_local_date=today_east,
        ),
    )
    await db_session.flush()
    await db_session.commit()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        patch_response = await client.patch(
            "/v1/me",
            headers=headers,
            json={"timezone": WESTMOST_TZ},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["user"]["timezone"] == WESTMOST_TZ

        session_response = await client.get("/v1/session/today", headers=headers)
        assert session_response.status_code == 200

        submit_response = await client.post(
            "/v1/attempts",
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            json={
                "exercise_id": str(exercise.id),
                "exercise_version": exercise.version,
                "answer": {"line": 1, "reason_id": "a"},
                "time_taken_ms": 1000,
            },
        )

    assert submit_response.status_code == 200
    body = submit_response.json()
    # The repair already marked "today" (under the new timezone) as
    # counted, so this submit is a same-day resubmit: no streak event, and
    # -- the whole point -- the streak must NOT have reset to 1.
    assert body["streak"] is None
    stats = await db_session.get(UserStats, user.id)
    assert stats.current_streak == 5


@pytest.mark.asyncio
async def test_same_timezone_patch_does_not_write_a_repair_event(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session, timezone=EASTMOST_TZ)
    db_session.add(
        UserStats(
            user_id=user.id,
            current_streak=2,
            longest_streak=2,
            last_active_local_date=local_date_for(EASTMOST_TZ),
        ),
    )
    await db_session.flush()
    await db_session.commit()

    await reconcile_streak_for_timezone_change(db_session, user, EASTMOST_TZ)
    await db_session.commit()

    assert await _streak_events(db_session, user.id) == []
