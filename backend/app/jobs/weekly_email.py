"""Weekly recap job (A3, D-137(8)).

Replaces the M7 placeholder this file used to be.

Sends on Monday at RECAP_LOCAL_HOUR in the user's own timezone, reporting the
ISO week that ENDED on Sunday. Monday because that is the first moment the week
being reported is complete: a Sunday-evening send would silently omit Sunday,
which is a recap that is wrong rather than merely early.

The hour is FIXED rather than the user's `reminder_local_time`, for two reasons.
It keeps the recap independent of the reminder schedule, which D-137(6) requires
so that a schedule change cannot alter consent; and it stops both of our emails
landing in the same minute for anyone whose reminder is set to the morning,
which is the "protect the channel" failure in its most literal form.

An empty week is never sent. It is closed as 'skipped' in the ledger instead.
"""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import exists
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.email.deliveries import eligible_recipients, recap_period_key
from app.email.dispatch import Candidate, SweepResult, run_sweep
from app.email.messages import build_recap_email
from app.email.recap import build_weekly_recap, week_bounds
from app.email.sender import EmailSender, OutboundEmail, get_email_sender
from app.models import EmailSuppression, User

logger = logging.getLogger(__name__)

KIND = "recap"


async def _find_candidates(session: AsyncSession, *, now: dt.datetime) -> list[Candidate]:
    settings = get_settings()

    suppressed = exists().where(
        EmailSuppression.user_id == User.id,
        EmailSuppression.kind.in_((KIND, "all")),
    )

    users = await session.scalars(
        eligible_recipients()
        .where(~suppressed)
        .order_by(User.id)
        .limit(settings.EMAIL_JOB_BATCH_SIZE),
    )

    # NOTE the deliberate absence of a reminder_local_time condition. The recap
    # is its own channel: a user who never set a reminder time still gets the
    # weekly recap unless they suppress it. Requiring a reminder time here would
    # silently couple the two, which is exactly the coupling D-137(6) forbids.
    candidates: list[Candidate] = []
    for user in users.all():
        try:
            local_now = now.astimezone(ZoneInfo(user.timezone))
        except ZoneInfoNotFoundError:
            logger.warning(
                "recap.bad_timezone",
                extra={"user_id": str(user.id), "timezone": user.timezone},
            )
            continue

        if local_now.weekday() != settings.RECAP_LOCAL_WEEKDAY:
            continue
        # Same wide-window reasoning as the reminder: at or past the hour, for
        # the rest of that local day. A tick that is late, or a deploy that
        # restarts the process over the hour boundary, must not cost a week.
        if local_now.hour < settings.RECAP_LOCAL_HOUR:
            continue

        candidates.append(
            Candidate(
                user_id=user.id,
                email=user.email,
                period_key=recap_period_key(local_now.date()),
            ),
        )

    return candidates


async def _build(session: AsyncSession, candidate: Candidate) -> OutboundEmail | None:
    # The period key names the week the recap is SENT in; the content is the
    # week before it. week_bounds() owns that offset so the two cannot drift.
    year, _, week = candidate.period_key.partition("-W")
    monday_of_send_week = dt.date.fromisocalendar(int(year), int(week), 1)
    week_start, week_end = week_bounds(monday_of_send_week)

    recap = await build_weekly_recap(
        session,
        candidate.user_id,
        week_start=week_start,
        week_end=week_end,
    )
    if recap.is_empty:
        # Returning None closes the period as 'skipped'. A report of nothing is
        # not a report, and "here is your week: nothing" is guilt copy however
        # it is worded (D-137(8)).
        return None

    return build_recap_email(to=candidate.email, user_id=candidate.user_id, recap=recap)


async def send_weekly_recaps(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None = None,
    *,
    now: dt.datetime | None = None,
) -> dict[str, int]:
    """One tick. Same off-switch and same failure isolation as the reminder."""
    moment = now or dt.datetime.now(dt.UTC)
    async with session_factory() as session:
        candidates = await _find_candidates(session, now=moment)

    if not candidates:
        return SweepResult().as_dict()

    result = await run_sweep(
        session_factory,
        sender or get_email_sender(),
        kind=KIND,
        candidates=candidates,
        build_message=_build,
    )
    logger.info("recap.tick", extra=result.as_dict())
    return result.as_dict()
