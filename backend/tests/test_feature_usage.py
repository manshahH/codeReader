"""feature_usage: the once-per-day grain, the never-raise property, and
cascade-delete-with-account (D-145(g))."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entitlements import Feature
from app.core.usage import record_feature_usage
from app.models import FeatureUsage, User
from tests.factories_m4 import (
    clean_m4_tables,  # noqa: F401 (autouse fixture, must be imported to activate)
    clean_redis,  # noqa: F401 (autouse fixture, must be imported to activate)
    m4_env,  # noqa: F401 (autouse fixture, must be imported to activate)
    make_user,
)


async def _count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(FeatureUsage))


@pytest.mark.asyncio
async def test_second_record_same_day_is_a_noop(db_session: AsyncSession) -> None:
    """The PK IS the once-per-day ceiling: two records for the same
    (user, feature, local day) leave exactly one row (ON CONFLICT DO NOTHING)."""
    user = await make_user(db_session)
    today = dt.date(2026, 7, 23)

    await record_feature_usage(
        db_session, user_id=user.id, feature=Feature.CHEAT_SHEET, local_date=today
    )
    await record_feature_usage(
        db_session, user_id=user.id, feature=Feature.CHEAT_SHEET, local_date=today
    )

    assert await _count(db_session) == 1


@pytest.mark.asyncio
async def test_a_new_local_day_is_a_new_row(db_session: AsyncSession) -> None:
    """The grain is per DAY, so the next day records again."""
    user = await make_user(db_session)
    for day in (dt.date(2026, 7, 23), dt.date(2026, 7, 24)):
        await record_feature_usage(
            db_session, user_id=user.id, feature=Feature.CHEAT_SHEET, local_date=day
        )
    assert await _count(db_session) == 2


@pytest.mark.asyncio
async def test_a_failing_insert_never_raises_and_leaves_the_session_usable(
    db_session: AsyncSession,
) -> None:
    """Negative (house rule): an insert that MUST fail -- here a user_id with no
    users row, so the FK is violated -- is swallowed, not raised, and the outer
    transaction survives (the savepoint scoped the rollback). An analytics gap
    must never fail a user action (D-145(g))."""
    ghost = uuid.uuid4()

    # Must not raise despite the FK violation.
    await record_feature_usage(
        db_session, user_id=ghost, feature=Feature.CHEAT_SHEET, local_date=dt.date(2026, 7, 23)
    )

    assert await _count(db_session) == 0  # nothing landed
    # The session is still usable: a real record afterward still works, proving
    # the failed write did not poison the transaction.
    user = await make_user(db_session)
    await record_feature_usage(
        db_session, user_id=user.id, feature=Feature.CHEAT_SHEET, local_date=dt.date(2026, 7, 23)
    )
    assert await _count(db_session) == 1


@pytest.mark.asyncio
async def test_rows_are_deleted_with_the_account(db_session: AsyncSession) -> None:
    """ON DELETE CASCADE: the row carries no content and follows the user out
    (D-120: consent that cannot be withdrawn in-product is not consent)."""
    user = await make_user(db_session)
    await record_feature_usage(
        db_session, user_id=user.id, feature=Feature.CHEAT_SHEET, local_date=dt.date(2026, 7, 23)
    )
    assert await _count(db_session) == 1

    await db_session.delete(await db_session.get(User, user.id))
    await db_session.flush()

    assert await _count(db_session) == 0
