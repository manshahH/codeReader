"""M7 partition-cron self-recovery: docs/04 warns that rows already sitting
in attempts_default must be moved out BEFORE creating the overlapping
monthly partition, "or the create fails". Before this fix, the job never
drained attempts_default and only ever created a single "next month"
partition, so a missed month could never be recovered -- the job would keep
trying to create only whatever "next month" currently was, permanently
skipping the gap.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.partitions import (
    count_attempts_default_rows,
    ensure_next_month_attempts_partition,
)
from app.models import Attempt
from tests.factories_m4 import (
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)


async def _partition_exists(db_session: AsyncSession, name: str) -> bool:
    result = await db_session.execute(
        text("SELECT count(*) FROM pg_class WHERE relname = :name"),
        {"name": name},
    )
    return result.scalar_one() == 1


@pytest.mark.asyncio
async def test_missed_month_in_attempts_default_recovers_instead_of_raising(
    db_session: AsyncSession,
) -> None:
    """db/schema.sql bootstraps attempts_2026_07 and attempts_2026_08 only.
    A row lands in September (no partition exists for it yet, so Postgres
    itself routes it into attempts_default -- exactly what happens in
    production when the cron is missed for a month). Running the job with
    reference_date=2026-10-05 must recover: it needs September (the gap),
    October, and November (next month) partitions, draining the stray row
    out of attempts_default along the way instead of raising.
    """
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    stray_created_at = dt.datetime(2026, 9, 15, 12, 0, tzinfo=dt.UTC)
    stray_attempt = Attempt(
        user_id=user.id,
        exercise_id=exercise.id,
        exercise_version=exercise.version,
        session_date=stray_created_at.date(),
        answer={"line": 1, "reason_id": "a"},
        grading_mode="deterministic",
        status="graded",
        is_correct=True,
        created_at=stray_created_at,
        graded_at=stray_created_at,
    )
    db_session.add(stray_attempt)
    await db_session.commit()

    assert await count_attempts_default_rows(db_session) == 1
    assert not await _partition_exists(db_session, "attempts_2026_09")

    result = await ensure_next_month_attempts_partition(
        db_session,
        reference_date=dt.date(2026, 10, 5),
    )
    await db_session.commit()

    assert result == "attempts_2026_11"
    for name in ("attempts_2026_09", "attempts_2026_10", "attempts_2026_11"):
        assert await _partition_exists(db_session, name), f"{name} was not created"

    # The stray row must have MOVED, not been lost or duplicated.
    assert await count_attempts_default_rows(db_session) == 0
    moved_count = await db_session.scalar(
        text("SELECT count(*) FROM attempts_2026_09 WHERE user_id = :uid"),
        {"uid": user.id},
    )
    assert moved_count == 1
    still_queryable = await db_session.get(Attempt, (stray_attempt.id, stray_created_at))
    assert still_queryable is not None
    assert still_queryable.is_correct is True


@pytest.mark.asyncio
async def test_run_with_no_gap_is_a_cheap_noop_on_existing_months(
    db_session: AsyncSession,
) -> None:
    """The common case (no missed month, attempts_default empty) must not
    regress: exactly one new partition (next month), no draining.
    """
    result = await ensure_next_month_attempts_partition(
        db_session,
        reference_date=dt.date(2026, 7, 20),
    )
    await db_session.commit()

    assert result == "attempts_2026_08"
    assert await _partition_exists(db_session, "attempts_2026_08")
    assert await count_attempts_default_rows(db_session) == 0


@pytest.mark.asyncio
async def test_rerunning_after_recovery_is_idempotent(db_session: AsyncSession) -> None:
    first = await ensure_next_month_attempts_partition(
        db_session,
        reference_date=dt.date(2026, 7, 20),
    )
    await db_session.commit()
    second = await ensure_next_month_attempts_partition(
        db_session,
        reference_date=dt.date(2026, 7, 20),
    )
    await db_session.commit()
    assert first == second == "attempts_2026_08"
