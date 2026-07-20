"""The send-once ledger and the suppression list (A3, D-137(2), (3), (6)).

This module is the frequency ceiling. Everything about "may we send" and "have
we already sent" lives here so that a future third notification kind cannot get
it subtly wrong by reimplementing the predicate at its own call site.

The claim is ONE atomic statement (see `claim_period`). That is the whole
mechanism: PostgreSQL arbitrates, not application logic, so two overlapping job
runs, a job that overlaps itself, and a job restarted mid-sweep all converge on
the same answer without an advisory lock.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import EmailSuppression, User

logger = logging.getLogger(__name__)


def eligible_recipients() -> Select[tuple[User]]:
    """The ONE definition of "we are allowed to mail this person" (D-137(1)).

    `users.email` already holds only a verified address (D-120), so this
    predicate is partly redundant with that invariant. It is written out anyway:
    "the column is only ever written with verified values" is an invariant held
    by a different module, and a job is the wrong place to depend on another
    module's discipline. `pending_email` is never selected here, or anywhere
    else in the notification path.

    Callers add the per-kind conditions (a reminder time, a suppression check,
    a period claim); nobody gets to skip these three.
    """
    return select(User).where(
        User.email.is_not(None),
        User.email_verified_at.is_not(None),
        User.deleted_at.is_(None),
    )


async def suppressed_kinds(session: AsyncSession, user_id: uuid.UUID) -> frozenset[str]:
    """Every kind this user has opted out of, with 'all' expanded.

    'all' is what a spam complaint means, so it is expanded here rather than
    left for each caller to remember -- a caller checking only for its own kind
    would happily mail someone who reported us as spam.
    """
    rows = await session.scalars(
        select(EmailSuppression.kind).where(EmailSuppression.user_id == user_id),
    )
    kinds = set(rows.all())
    if "all" in kinds:
        kinds.update({"reminder", "recap"})
    return frozenset(kinds)


async def is_suppressed(session: AsyncSession, user_id: uuid.UUID, kind: str) -> bool:
    return kind in await suppressed_kinds(session, user_id)


async def email_preferences(session: AsyncSession, user_id: uuid.UUID) -> dict[str, bool]:
    """The owner-visible consent state, for GET /me and the Profile toggles.

    Phrased POSITIVELY (`reminders_enabled`) while the table stores the
    negative (a suppression row). The UI asks "is this on", and making the
    client invert a suppression is how a UI ends up showing the opposite of the
    truth after someone refactors the field name.

    This is CONSENT only. It deliberately does not fold in
    `reminder_local_time`: a user can have reminders consented and no time set,
    which is a real and distinct state the Profile screen has to render
    differently from "turned off" (D-137(6)).
    """
    suppressed = await suppressed_kinds(session, user_id)
    return {
        "reminders_enabled": "reminder" not in suppressed,
        "recap_enabled": "recap" not in suppressed,
    }


async def suppress(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    *,
    reason: str = "unsubscribe",
    source: str = "email_link",
) -> None:
    """Opt out. IDEMPOTENT, which is a hard requirement rather than a nicety.

    A mail provider's one-click unsubscribe may be delivered more than once,
    and a user may click the link in two different emails. Neither may be an
    error: an unsubscribe that 500s on the second press reads to the user as
    "it did not work", and the next thing they do is report us as spam.

    ON CONFLICT DO NOTHING rather than an upsert, so the ORIGINAL reason and
    source survive. If a bounce suppressed this user first, a later click must
    not rewrite the record to say a human chose it.
    """
    await session.execute(
        text(
            """
            INSERT INTO email_suppressions (user_id, kind, reason, source)
            VALUES (:user_id, :kind, :reason, :source)
            ON CONFLICT (user_id, kind) DO NOTHING
            """,
        ),
        {"user_id": str(user_id), "kind": kind, "reason": reason, "source": source},
    )


async def unsuppress(session: AsyncSession, user_id: uuid.UUID, kind: str) -> None:
    """Opt back in. The ONLY path that removes a suppression, and it is reached
    exclusively from the authenticated Profile control (D-137(6)).

    Nothing in the job path calls this, and there is no expiry that would call
    it implicitly. Re-consent has to be a deliberate act by the account owner.
    """
    await session.execute(
        text("DELETE FROM email_suppressions WHERE user_id = :user_id AND kind = :kind"),
        {"user_id": str(user_id), "kind": kind},
    )


async def claim_period(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    period_key: str,
) -> bool:
    """Try to become the one sender for (user, kind, period). THE CEILING.

    Returns True only if the caller now owns the send. Every caller MUST treat
    False as "skip, someone else has this period", and the ledger row is
    committed by the caller before any provider call (D-137(3)).

    One statement, and it has to be one statement. A read-then-insert would
    race; a SELECT ... FOR UPDATE would need a row that may not exist yet.
    INSERT ... ON CONFLICT DO UPDATE ... WHERE does both jobs at once:

    * No row yet -> INSERT wins, attempts = 1. A concurrent second caller hits
      the conflict and falls to the DO UPDATE, whose WHERE is false for a row
      that is 'claimed', so it updates nothing and RETURNING yields no row.
    * Row is 'failed' -> the WHERE passes while the attempt budget and the
      retry window both hold, so this becomes a bounded retry.
    * Row is 'sent', 'skipped', 'claimed', or a 'failed' row that is out of
      attempts or out of the window -> the WHERE is false, no row returned,
      caller skips.

    The retry WINDOW is not decoration. The second send-once layer is Resend's
    Idempotency-Key, honoured for 24 hours; past that a retry is no longer
    provably free of duplicates, so we stop instead of guessing (D-137(4)).
    """
    settings = get_settings()
    result = await session.execute(
        text(
            """
            INSERT INTO email_deliveries
                (user_id, kind, period_key, status, attempts, claimed_at, updated_at)
            VALUES (:user_id, :kind, :period_key, 'claimed', 1, now(), now())
            ON CONFLICT (user_id, kind, period_key) DO UPDATE
               SET status     = 'claimed',
                   attempts   = email_deliveries.attempts + 1,
                   claimed_at = now(),
                   updated_at = now()
             WHERE email_deliveries.status = 'failed'
               AND email_deliveries.attempts < :max_attempts
               AND email_deliveries.claimed_at > now() - make_interval(hours => :window_h)
            RETURNING attempts
            """,
        ),
        {
            "user_id": str(user_id),
            "kind": kind,
            "period_key": period_key,
            "max_attempts": settings.EMAIL_SEND_MAX_ATTEMPTS,
            "window_h": settings.EMAIL_SEND_RETRY_WINDOW_H,
        },
    )
    return result.first() is not None


async def _finish(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    period_key: str,
    *,
    status: str,
    last_error: str | None = None,
) -> None:
    await session.execute(
        text(
            """
            UPDATE email_deliveries
               SET status     = :status,
                   last_error = :last_error,
                   sent_at    = CASE WHEN :status = 'sent' THEN now() ELSE sent_at END
             WHERE user_id = :user_id AND kind = :kind AND period_key = :period_key
            """,
        ),
        {
            "user_id": str(user_id),
            "kind": kind,
            "period_key": period_key,
            "status": status,
            "last_error": last_error,
        },
    )


async def mark_sent(
    session: AsyncSession, user_id: uuid.UUID, kind: str, period_key: str
) -> None:
    """Terminal. The provider accepted."""
    await _finish(session, user_id, kind, period_key, status="sent")


async def mark_failed(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    period_key: str,
    *,
    error: str,
) -> None:
    """A DEFINITE failure, committed so the period becomes retryable.

    `error` must be an exception TYPE name, never a message and never a body:
    an httpx error can carry the request body, and that body is somebody's
    mail (D-120's logging discipline).
    """
    await _finish(session, user_id, kind, period_key, status="failed", last_error=error)


async def mark_skipped(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    period_key: str,
    *,
    note: str,
) -> None:
    """Terminal, and deliberately not a send: an empty recap week (D-137(8)).

    Recorded rather than left absent so the period is settled and every later
    tick that day stops re-deriving the same nothing.
    """
    await _finish(session, user_id, kind, period_key, status="skipped", last_error=note)


def reminder_period_key(local_date: dt.date) -> str:
    """The user-LOCAL calendar date. One reminder per local day, by construction.

    DST is a non-event for this key: a 23- or 25-hour day is still exactly one
    calendar date (D-137(5)).
    """
    return local_date.isoformat()


def recap_period_key(local_date: dt.date) -> str:
    """ISO year-week of the user-local date, e.g. '2026-W29'.

    isocalendar() rather than strftime('%G-W%V'): the %G/%V directives are not
    portable across platforms (Windows' C runtime does not implement them), and
    this code has to behave identically on a dev box and in CI.
    """
    iso = local_date.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"
