"""Streak reconciliation on a timezone change (M7; docs/05 section 3:
"changing timezone never retroactively breaks a streak").

A user-local date is a function of both `now` and `users.timezone`; changing
timezone changes what "today" resolves to for the same instant. A westward
change (e.g. Asia/Kiritimati UTC+14 -> Pacific/Midway UTC-11) can move the
new local "today" EARLIER than `user_stats.last_active_local_date`, which
was recorded under the OLD timezone. The next submit computes `today` under
the NEW timezone and finds `last_active_local_date` sitting in what looks
like the future -- it satisfies neither `== today` (already counted today)
nor `== today - 1 day` (consecutive) in attempts/service.py's streak
transition, so the streak silently resets to 1 even though the user did not
miss a day.

Fix: whenever a timezone change would move the local-date boundary BACKWARD
past an already-counted day, clamp `last_active_local_date` down to the new
local `today` (the user genuinely was active "today" under the new clock
too) and write a `streak_events` row with event='repaired' -- the schema
explicitly reserves that value for exactly this, and `current_streak`
itself is never touched, only the date bookkeeping. A forward (eastward)
change is left alone: it's handled correctly by the existing extend/reset
day-math already, and docs/05 only promises the boundary never moves
backward.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezones import local_date_for
from app.models import StreakEvent, User, UserStats


async def reconcile_streak_for_timezone_change(
    db: AsyncSession,
    user: User,
    new_timezone: str,
    *,
    now: dt.datetime | None = None,
) -> None:
    """Call BEFORE assigning `user.timezone = new_timezone` -- compares the
    new timezone's "today" against the stats row recorded under the OLD
    one. No-ops (no row read, no event written) when there's no prior
    activity to protect or the boundary didn't move backward.
    """
    if new_timezone == user.timezone:
        return

    stats = await db.get(UserStats, user.id)
    if stats is None or stats.last_active_local_date is None:
        return

    new_today = local_date_for(new_timezone, now=now)
    if new_today >= stats.last_active_local_date:
        return

    previous_local_date = stats.last_active_local_date
    stats.last_active_local_date = new_today
    db.add(
        StreakEvent(
            user_id=user.id,
            event="repaired",
            from_value=stats.current_streak,
            to_value=stats.current_streak,
            local_date=new_today,
            note=(
                f"timezone change {user.timezone!r} -> {new_timezone!r} moved the "
                f"local-date boundary backward from {previous_local_date.isoformat()} "
                f"to {new_today.isoformat()}; last_active_local_date repaired to "
                "avoid a false streak reset"
            ),
        ),
    )
    await db.flush()
