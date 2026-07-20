"""Daily reminder job (A3, D-137).

Finds users whose local clock has passed their `reminder_local_time` today, who
have a verified address, who are not suppressed, and who have not already
practised today. Sends at most one reminder per user per user-local day, and the
ledger (not this module) is what guarantees the "at most one".

THE ELIGIBILITY WINDOW IS WIDE ON PURPOSE, and it is the one thing here most
likely to look like a bug. Eligibility is "local time is at or past
reminder_local_time", for the whole remainder of the local day -- not "the
reminder time just passed in the last tick". A narrow window silently drops a
day whenever a tick is late, a deploy restarts the process, or DST skips the
hour the reminder was set in (D-137(5)). The wide window only works BECAUSE the
ledger makes a second send impossible; with a timestamp column it would mail
someone every five minutes all evening.
"""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.email.deliveries import eligible_recipients, reminder_period_key
from app.email.dispatch import Candidate, SweepResult, run_sweep
from app.email.messages import build_reminder_email
from app.email.sender import EmailSender, OutboundEmail, get_email_sender
from app.models import DailySession, EmailSuppression, User, UserStats

logger = logging.getLogger(__name__)

KIND = "reminder"


async def _find_candidates(session: AsyncSession, *, now: dt.datetime) -> list[Candidate]:
    settings = get_settings()

    # Suppression is filtered in SQL rather than per row, so a suppressed user
    # is never even loaded. 'all' is included because that is what a spam
    # complaint means (D-137(6)).
    suppressed = exists().where(
        EmailSuppression.user_id == User.id,
        EmailSuppression.kind.in_((KIND, "all")),
    )

    rows = await session.execute(
        eligible_recipients()
        .add_columns(UserStats.last_active_local_date)
        .outerjoin(UserStats, UserStats.user_id == User.id)
        .where(
            # NULL reminder_local_time means reminders off, and it has meant
            # that since the column existed (db/schema.sql). This is the
            # SCHEDULE half; the suppression above is the CONSENT half, and
            # both are required (D-137(6)).
            User.reminder_local_time.is_not(None),
            ~suppressed,
        )
        # Deterministic sweep order, so a per-tick cap always makes forward
        # progress through the same sequence instead of resampling.
        .order_by(User.id)
        .limit(settings.EMAIL_JOB_BATCH_SIZE),
    )

    candidates: list[Candidate] = []
    for user, last_active in rows.all():
        try:
            local_now = now.astimezone(ZoneInfo(user.timezone))
        except ZoneInfoNotFoundError:
            # A timezone we cannot resolve is a data problem for one user, not
            # a reason to abandon the sweep for everyone else.
            logger.warning(
                "reminders.bad_timezone",
                extra={"user_id": str(user.id), "timezone": user.timezone},
            )
            continue

        local_date = local_now.date()

        # Already practised today, so there is nothing to remind them about.
        # Read from user_stats.last_active_local_date, which is the SAME signal
        # the streak transition uses (attempts/service.py), so a day that counts
        # for the streak is exactly a day that suppresses the reminder. Deriving
        # it independently here would let the two disagree.
        if last_active is not None and last_active >= local_date:
            continue

        if local_now.time() < user.reminder_local_time:
            continue

        candidates.append(
            Candidate(
                user_id=user.id,
                email=user.email,
                period_key=reminder_period_key(local_date),
            ),
        )

    return candidates


async def _build(session: AsyncSession, candidate: Candidate) -> OutboundEmail | None:
    # Read the session only if it already exists. Calling the session builder
    # here would CREATE today's session as a side effect of reminding someone
    # that one exists, which would corrupt the "transient empty session" and
    # first-visit-builds-the-session behaviour the app depends on.
    row = await session.scalar(
        select(DailySession).where(
            DailySession.user_id == candidate.user_id,
            DailySession.session_date == dt.date.fromisoformat(candidate.period_key),
        ),
    )
    count = len(row.exercise_list) if row is not None and row.exercise_list else None
    return build_reminder_email(to=candidate.email, user_id=candidate.user_id, exercise_count=count)


async def send_daily_reminders(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None = None,
    *,
    now: dt.datetime | None = None,
) -> dict[str, int]:
    """One tick. Returns counters; never raises for a single recipient.

    `sender` defaults to get_email_sender(), which is the A2 off-switch: with
    EMAIL_SENDING_ENABLED false this is a DisabledEmailSender that never
    constructs a request. The ledger still fills in, so the whole flow is
    walkable locally with nothing leaving the process.
    """
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
    logger.info("reminders.tick", extra=result.as_dict())
    return result.as_dict()
