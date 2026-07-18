"""D-124: a repair that would not beat the current streak is never offered.

Found by using the app: the dashboard read "Restore your 1-day streak" while the
current streak was already 1. A no-op presented as a benefit, and worse than
cosmetic, because a reset is repairable AT MOST ONCE (D-116) -- accepting the
offer would burn the user's only chance to repair that reset in exchange for
nothing.

Gated in the API rather than the UI, so `repair_available` is false and no
client can render the offer at all. The route itself also refuses, because
hiding an affordance is not the same as preventing the action.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.models import StreakEvent, UserStats
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_user,
)


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


async def _plant_reset(
    db: AsyncSession, user_id: uuid.UUID, *, lost: int, current_streak: int
) -> None:
    """A repairable reset that would restore `lost + run`, with the user's
    streak currently at `current_streak`."""
    today = dt.datetime.now(dt.UTC).date()
    db.add(
        StreakEvent(
            user_id=user_id,
            event="reset",
            from_value=lost,
            to_value=1,
            local_date=today,
            note="[test]",
        ),
    )
    db.add(
        UserStats(
            user_id=user_id,
            current_streak=current_streak,
            longest_streak=max(current_streak, lost),
            streak_freezes=2,
            last_active_local_date=today,
        ),
    )
    await db.flush()
    await db.commit()


@pytest.mark.asyncio
async def test_no_repair_offered_when_it_would_not_beat_the_current_streak(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """THE REPORTED BUG: restore value 1, current streak already 1."""
    user = await make_user(db_session)
    # lost=0 + run=1 -> restores_to == 1, which is exactly the current streak.
    await _plant_reset(db_session, user.id, lost=0, current_streak=1)

    stats = (await client.get("/v1/me/stats", headers=auth_headers(user))).json()

    assert stats["repair_available"] is False, "a no-op repair must not be advertised"
    assert stats["repair_restores_to"] is None
    # D-116(b)'s identity must survive the change: the two can never disagree.
    assert stats["repair_available"] == (stats["repair_restores_to"] is not None)


@pytest.mark.asyncio
async def test_the_repair_route_refuses_a_no_op_even_if_called_directly(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """NEGATIVE: hiding the button is not the same as preventing the action.

    A stale tab, a replayed request or a hand-rolled client must not be able to
    spend the one-shot repair on a restore that gains nothing.
    """
    user = await make_user(db_session)
    await _plant_reset(db_session, user.id, lost=0, current_streak=1)

    response = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": str(uuid.uuid4())},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_repairable"

    stats = (await client.get("/v1/me/stats", headers=auth_headers(user))).json()
    assert stats["current_streak"] == 1, "the streak must be untouched"


@pytest.mark.asyncio
async def test_a_repair_that_genuinely_gains_days_is_still_offered(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The positive control: the gate must not suppress real repairs.

    Without this, a bug that disabled repair entirely would pass the two tests
    above and look like a fix.
    """
    user = await make_user(db_session)
    # lost=7 + run=1 -> restores_to == 8, well above the current streak of 1.
    await _plant_reset(db_session, user.id, lost=7, current_streak=1)

    stats = (await client.get("/v1/me/stats", headers=auth_headers(user))).json()
    assert stats["repair_available"] is True
    assert stats["repair_restores_to"] == 8

    response = await client.post(
        "/v1/streak/repair",
        headers={**auth_headers(user), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 200
    assert response.json()["current_streak"] == 8

    after = (await client.get("/v1/me/stats", headers=auth_headers(user))).json()
    assert after["current_streak"] == 8
    # And the one-shot is now spent, so it is no longer offered.
    assert after["repair_available"] is False
