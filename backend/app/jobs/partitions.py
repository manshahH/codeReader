from __future__ import annotations

import datetime as dt

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _first_day_of_next_month(reference_date: dt.date) -> dt.date:
    first_of_month = reference_date.replace(day=1)
    if first_of_month.month == 12:
        return dt.date(first_of_month.year + 1, 1, 1)
    return dt.date(first_of_month.year, first_of_month.month + 1, 1)


def _first_day_after_month(month_start: dt.date) -> dt.date:
    if month_start.month == 12:
        return dt.date(month_start.year + 1, 1, 1)
    return dt.date(month_start.year, month_start.month + 1, 1)


async def ensure_next_month_attempts_partition(
    session: AsyncSession,
    reference_date: dt.date | None = None,
) -> str:
    month_start = _first_day_of_next_month(reference_date or dt.datetime.now(dt.UTC).date())
    month_end = _first_day_after_month(month_start)
    partition_name = f"attempts_{month_start:%Y_%m}"

    await session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF attempts
            FOR VALUES FROM ('{month_start.isoformat()}') TO ('{month_end.isoformat()}')
            """,
        ),
    )
    return partition_name


async def count_attempts_default_rows(session: AsyncSession) -> int:
    result = await session.execute(text("SELECT count(*) FROM attempts_default"))
    return int(result.scalar_one())
