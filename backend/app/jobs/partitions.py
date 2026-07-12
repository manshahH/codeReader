"""Monthly attempts partition management (M7 audit fix).

Two bugs closed here, both from docs/04's own warning: "move [attempts_default
rows] out BEFORE creating the overlapping monthly partition or the create
fails."

1. The job only ever created NEXT month's partition. If it was never
   invoked for two+ consecutive months (a deploy gap, JOBS_ENABLED=false for
   a while, ...), attempts for every skipped month land in attempts_default,
   and a two-month gap could never close: the job would try to create only
   the month after "now", permanently skipping the months in between.
2. `count_attempts_default_rows` existed but was never called from the
   partition-creation path -- it was a diagnostic printed alongside partition
   creation, not a precondition acted on. A `CREATE TABLE ... PARTITION OF
   attempts FOR VALUES FROM (...) TO (...)` for a month that already has
   rows sitting in attempts_default fails outright (Postgres refuses a
   range partition that would overlap rows already present in DEFAULT), so
   once a gap opened, every subsequent run raised instead of recovering.

Fix: `ensure_next_month_attempts_partition` now walks every month from the
last existing partition through next month (closing gaps of any size, not
just one), and for each month first checks whether attempts_default holds
rows in that month's range. If it does, it logs loudly, moves those rows
onto a plain table (`CREATE TABLE ... (LIKE attempts INCLUDING ALL)` +
`DELETE ... RETURNING` + `INSERT ... OVERRIDING SYSTEM VALUE`), and attaches
that table as the partition (`ALTER TABLE attempts ATTACH PARTITION`) --
identical end state to `CREATE TABLE ... PARTITION OF`, but reachable when
DEFAULT already has conflicting rows. The common case (attempts_default
empty for the target month) takes the cheap direct `CREATE TABLE ...
PARTITION OF` path unchanged.
"""

from __future__ import annotations

import datetime as dt
import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_PARTITION_NAME_RE = re.compile(r"^attempts_(\d{4})_(\d{2})$")
# Safety cap on how many months a single run will backfill, so a detection
# bug can never turn this into an unbounded loop; a gap this size would mean
# the job was down for six years.
_MAX_MONTHS_PER_RUN = 72


def _first_day_of_next_month(reference_date: dt.date) -> dt.date:
    first_of_month = reference_date.replace(day=1)
    if first_of_month.month == 12:
        return dt.date(first_of_month.year + 1, 1, 1)
    return dt.date(first_of_month.year, first_of_month.month + 1, 1)


def _first_day_after_month(month_start: dt.date) -> dt.date:
    if month_start.month == 12:
        return dt.date(month_start.year + 1, 1, 1)
    return dt.date(month_start.year, month_start.month + 1, 1)


async def _existing_partition_months(session: AsyncSession) -> list[dt.date]:
    rows = await session.execute(
        text(
            "SELECT relname FROM pg_class "
            "WHERE relkind IN ('r', 'p') AND relname ~ '^attempts_[0-9]{4}_[0-9]{2}$'",
        ),
    )
    months: list[dt.date] = []
    for (relname,) in rows.all():
        match = _PARTITION_NAME_RE.match(relname)
        if match:
            months.append(dt.date(int(match.group(1)), int(match.group(2)), 1))
    return sorted(months)


async def count_attempts_default_rows(session: AsyncSession) -> int:
    result = await session.execute(text("SELECT count(*) FROM attempts_default"))
    return int(result.scalar_one())


async def _count_attempts_default_rows_in_range(
    session: AsyncSession,
    month_start: dt.date,
    month_end: dt.date,
) -> int:
    result = await session.execute(
        text(
            "SELECT count(*) FROM attempts_default "
            "WHERE created_at >= :start AND created_at < :end",
        ),
        {"start": month_start, "end": month_end},
    )
    return int(result.scalar_one())


async def _create_partition_for_month(session: AsyncSession, month_start: dt.date) -> str:
    month_end = _first_day_after_month(month_start)
    partition_name = f"attempts_{month_start:%Y_%m}"
    bounds = {"start": month_start, "end": month_end}
    # FOR VALUES FROM/TO and ATTACH PARTITION bounds are DDL, not DML --
    # Postgres does not accept query parameters there, so these two literals
    # are interpolated directly (as the original code already did with
    # .isoformat()); both dates come only from _first_day_of_next_month's
    # own arithmetic, never from external input. The DML below (the actual
    # row DELETE/INSERT) uses real bind parameters throughout.
    from_literal = month_start.isoformat()
    to_literal = month_end.isoformat()

    overlapping = await _count_attempts_default_rows_in_range(session, month_start, month_end)
    if overlapping == 0:
        await session.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF attempts "
                f"FOR VALUES FROM ('{from_literal}') TO ('{to_literal}')",
            ),
        )
        return partition_name

    # ALERT-worthy: attempts_default should be empty in steady state. Its
    # only job is absorbing writes during a missed-partition window.
    logger.warning(
        "attempts_default_has_rows: draining %d row(s) for %s before creating the "
        "overlapping partition (a direct CREATE TABLE ... PARTITION OF would fail)",
        overlapping,
        partition_name,
        extra={
            "event": "attempts_default_has_rows",
            "partition": partition_name,
            "row_count": overlapping,
        },
    )
    await session.execute(
        text(f"CREATE TABLE IF NOT EXISTS {partition_name} (LIKE attempts INCLUDING ALL)"),
    )
    await session.execute(
        text(
            f"""
            WITH moved AS (
                DELETE FROM attempts_default
                WHERE created_at >= :start AND created_at < :end
                RETURNING *
            )
            INSERT INTO {partition_name} OVERRIDING SYSTEM VALUE
            SELECT * FROM moved
            """,
        ),
        bounds,
    )
    await session.execute(
        text(
            f"ALTER TABLE attempts ATTACH PARTITION {partition_name} "
            f"FOR VALUES FROM ('{from_literal}') TO ('{to_literal}')",
        ),
    )
    return partition_name


async def ensure_next_month_attempts_partition(
    session: AsyncSession,
    reference_date: dt.date | None = None,
) -> str:
    """Ensures a partition exists for every month from the last one that
    already exists through next month (inclusive), draining attempts_default
    as needed along the way. Returns next month's partition name (the
    caller-visible contract is unchanged; a normal run with no gap creates
    exactly that one partition, same as before).
    """
    today = reference_date or dt.datetime.now(dt.UTC).date()
    next_month = _first_day_of_next_month(today)

    existing_months = await _existing_partition_months(session)
    if existing_months:
        start_month = _first_day_of_next_month(existing_months[-1])
    else:
        # No partitions found at all (shouldn't happen -- db/schema.sql
        # bootstraps two -- but never scan backward from year zero).
        start_month = today.replace(day=1)

    months_to_create: list[dt.date] = []
    month = start_month
    while month <= next_month and len(months_to_create) < _MAX_MONTHS_PER_RUN:
        months_to_create.append(month)
        month = _first_day_of_next_month(month)

    if len(months_to_create) > 1:
        logger.warning(
            "attempts_partition_gap_recovered: creating %d missed partition(s): %s",
            len(months_to_create),
            ", ".join(f"attempts_{m:%Y_%m}" for m in months_to_create),
        )

    partition_name = f"attempts_{next_month:%Y_%m}"
    for target_month in months_to_create:
        partition_name = await _create_partition_for_month(session, target_month)
    return partition_name


async def _main() -> None:
    from app.db import create_engine, create_session_factory

    engine = create_engine()
    try:
        async with create_session_factory(engine)() as session:
            partition_name = await ensure_next_month_attempts_partition(session)
            default_rows = await count_attempts_default_rows(session)
            await session.commit()
        print(f"partitions: ensured {partition_name}; attempts_default rows={default_rows}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
