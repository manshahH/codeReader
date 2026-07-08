from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo


def local_date_for(tz_name: str, now: dt.datetime | None = None) -> dt.date:
    """The user-local calendar date `now` falls on, per their IANA timezone."""
    moment = now or dt.datetime.now(dt.UTC)
    return moment.astimezone(ZoneInfo(tz_name)).date()


def local_day_end_utc(tz_name: str, local_date: dt.date) -> dt.datetime:
    """UTC instant of the start of the day after `local_date` in `tz_name`.

    Anything with a timestamp strictly before this instant falls on or before
    `local_date` from that user's perspective -- used to decide which
    spaced-repetition concepts are "due today" regardless of what wall-clock
    time on the server the session happens to be built at.
    """
    next_local_midnight = dt.datetime.combine(
        local_date + dt.timedelta(days=1),
        dt.time.min,
        tzinfo=ZoneInfo(tz_name),
    )
    return next_local_midnight.astimezone(dt.UTC)
