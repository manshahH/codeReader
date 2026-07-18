"""A1 streak safety net: freeze accrual, freeze consumption, repair, outage fill.

The load-bearing rule is D-116: a "covered day" is read from the streak_events
ledger, not inferred from the freeze balance. A missed local date is covered if
a `freeze_used` row already exists for it, whatever wrote that row (a prior
outage fill, or an earlier consumption). The balance pays only for the
UNCOVERED remainder, and both the balance test and STREAK_FREEZE_MAX apply to
that remainder rather than to total gap size. This is what lets an ops outage
fill a day for everyone without spending anybody's balance while still using
one mechanism, one currency, one source of truth.

Consumption itself stays all-or-nothing per docs/10: if the uncovered
remainder exceeds what the balance can pay, nothing is spent and the caller
falls through to the ordinary reset.

`from_value == to_value` on freeze_used/repaired/adjusted rows follows the
convention jobs/streak_recon.py already established: those columns always mean
"streak value", so a row that records bookkeeping rather than a streak change
carries the value unchanged and explains itself in `note`.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.core.timezones import local_date_for
from app.models import StreakEvent, User, UserStats

IDEMPOTENCY_NAMESPACE = "streak_repair"

# D-116(c): event='repaired' is also written by jobs/streak_recon.py for the
# timezone-boundary case. A repair anchored to a specific reset row stamps that
# reset's primary key into `note`, so the "a reset is repairable at most once"
# check matches only genuine repairs of THAT reset and an unrelated timezone
# reconciliation can never silently consume a user's one repair.
_ANCHOR_PREFIX = "[repair:anchor="


def _anchor_marker(reset_event_id: int) -> str:
    return f"{_ANCHOR_PREFIX}{reset_event_id}]"


def new_user_stats(user_id: uuid.UUID) -> UserStats:
    """Every UserStats row is born holding the starting freeze balance (A1).

    The DB default stays 0 so no migration is needed and pre-A1 rows are not
    retroactively granted anything; the grant is a property of creating the
    row, which is why it lives here and not in the model.
    """
    return UserStats(user_id=user_id, streak_freezes=get_settings().STREAK_FREEZE_START)


def missed_dates(last_active: dt.date, today: dt.date) -> list[dt.date]:
    """The local dates strictly between last_active and today."""
    span = (today - last_active).days
    return [last_active + dt.timedelta(days=offset) for offset in range(1, span)]


async def covered_dates(
    db: AsyncSession,
    user_id: uuid.UUID,
    dates: list[dt.date],
) -> set[dt.date]:
    """Which of `dates` already carry a freeze_used row (D-116)."""
    if not dates:
        return set()
    rows = await db.execute(
        select(StreakEvent.local_date).where(
            StreakEvent.user_id == user_id,
            StreakEvent.event == "freeze_used",
            StreakEvent.local_date.in_(dates),
        ),
    )
    return {row[0] for row in rows.all()}


async def try_cover_gap(
    db: AsyncSession,
    user_id: uuid.UUID,
    stats: UserStats,
    last_active: dt.date,
    today: dt.date,
) -> bool:
    """Attempt to save a streak across a gap. Returns True if the gap is fully
    covered (caller should proceed to today's `extended` transition), False if
    it is not (caller resets, unchanged). Writes nothing and spends nothing
    when it returns False -- a freeze never partially covers a gap.
    """
    settings = get_settings()
    missed = missed_dates(last_active, today)
    if not missed:
        return False

    already = await covered_dates(db, user_id, missed)
    uncovered = [day for day in missed if day not in already]

    # D-116: the cap and the balance both apply to the UNCOVERED remainder.
    # An outage-covered day is free and does not consume the cap. When every
    # missed day is already covered, uncovered is empty and this passes at a
    # zero balance, which is exactly the outage promise.
    payable = min(stats.streak_freezes, settings.STREAK_FREEZE_MAX)
    if len(uncovered) > payable:
        return False

    stats.streak_freezes -= len(uncovered)
    for day in uncovered:
        db.add(
            StreakEvent(
                user_id=user_id,
                event="freeze_used",
                from_value=stats.current_streak,
                to_value=stats.current_streak,
                local_date=day,
                note=(
                    f"streak freeze spent to cover missed day {day.isoformat()}; "
                    f"streak_freezes {stats.streak_freezes + 1} -> {stats.streak_freezes}"
                ),
            ),
        )
    return True


async def accrue_freeze_if_earned(
    db: AsyncSession,
    user_id: uuid.UUID,
    stats: UserStats,
    today: dt.date,
) -> bool:
    """+1 freeze every STREAK_FREEZE_EARN_EVERY consecutive active days, never
    above the cap. Call after an `extended` transition has set current_streak.
    Writes an `adjusted` row so the ledger explains the balance. Returns True
    if a freeze was granted.
    """
    settings = get_settings()
    every = settings.STREAK_FREEZE_EARN_EVERY
    if every <= 0 or stats.current_streak <= 0 or stats.current_streak % every != 0:
        return False
    # At the cap: no row, no change. The milestone is simply not a grant.
    if stats.streak_freezes >= settings.STREAK_FREEZE_MAX:
        return False

    before = stats.streak_freezes
    stats.streak_freezes = before + 1
    db.add(
        StreakEvent(
            user_id=user_id,
            event="adjusted",
            from_value=stats.current_streak,
            to_value=stats.current_streak,
            local_date=today,
            note=(
                # "streak milestone", NOT "consecutive active days": a frozen
                # day counts toward the streak without the user being active,
                # so an activity claim here would be false in the ledger.
                f"freeze earned at streak milestone {stats.current_streak} "
                f"(every {every}); streak_freezes {before} -> {stats.streak_freezes}"
            ),
        ),
    )
    return True


async def outage_freeze(db: AsyncSession, local_date: dt.date) -> dict:
    """Fill `local_date` with a freeze_used row for every user with recorded
    activity, WITHOUT spending balance and WITHOUT touching current_streak.

    D-116: this is a pure ledger write. The protection is realized lazily at
    each user's next submit, where try_cover_gap sees the row and treats the
    day as covered. That is what makes it safe to run over everyone: it can
    never manufacture a streak, because a user who was already inactive for a
    week gets exactly one of their seven missed days covered and still resets.

    One set-based statement rather than a per-user loop (see D-116(a): there is
    no bulk pattern in jobs/streak_recon.py to mirror). The NOT EXISTS clause
    is the "never write a duplicate freeze_used for a covered date" rule, which
    also makes re-running the endpoint for the same date a no-op.
    """
    inserted = await db.execute(
        text(
            """
            INSERT INTO streak_events
                (user_id, event, from_value, to_value, local_date, note)
            SELECT us.user_id, 'freeze_used', us.current_streak, us.current_streak,
                   :local_date, 'outage'
            FROM user_stats us
            WHERE us.last_active_local_date IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM streak_events se
                  WHERE se.user_id = us.user_id
                    AND se.local_date = :local_date
                    AND se.event = 'freeze_used'
              )
            """,
        ),
        {"local_date": local_date},
    )
    await db.commit()
    return {"local_date": local_date.isoformat(), "users_covered": inserted.rowcount}


_BACKFILL_MARKER = "[a1:initial-grant]"


async def grant_initial_freezes(db: AsyncSession, local_date: dt.date) -> dict:
    """One-time backfill of the starting freeze balance for users whose
    user_stats row predates A1 (D-118).

    Idempotent on two independent guards, both needed. `streak_freezes < grant`
    skips anyone already at or above the starting balance. The marker check
    skips anyone already granted, which is the one that matters on a re-run
    months later: by then a granted user may have legitimately SPENT down to 0,
    and the balance test alone would happily re-grant them.

    Capped at min(START, MAX) and never lowers an existing balance. Writes one
    `adjusted` row per user so the ledger explains where the balance came from,
    same as ordinary accrual.
    """
    settings = get_settings()
    grant = min(settings.STREAK_FREEZE_START, settings.STREAK_FREEZE_MAX)
    note = (
        f"A1 initial freeze grant: balance raised to {grant} for an account "
        f"created before the streak safety net shipped {_BACKFILL_MARKER}"
    )
    granted = await db.execute(
        text(
            """
            WITH updated AS (
                UPDATE user_stats us
                SET streak_freezes = :grant
                WHERE us.streak_freezes < :grant
                  AND NOT EXISTS (
                      SELECT 1 FROM streak_events se
                      WHERE se.user_id = us.user_id
                        AND se.event = 'adjusted'
                        AND se.note LIKE '%' || :marker || '%'
                  )
                RETURNING us.user_id, us.current_streak
            )
            INSERT INTO streak_events
                (user_id, event, from_value, to_value, local_date, note)
            SELECT user_id, 'adjusted', current_streak, current_streak, :local_date, :note
            FROM updated
            """,
        ),
        {
            "grant": grant,
            "marker": _BACKFILL_MARKER,
            "local_date": local_date,
            "note": note,
        },
    )
    await db.commit()
    return {"granted_to": granted.rowcount, "balance": grant}


@dataclass(frozen=True)
class RestorableReset:
    """A reset that can still be repaired, plus everything needed to do it."""

    reset_id: int
    from_value: int
    local_date: dt.date
    run: int

    @property
    def restores_to(self) -> int:
        """The unbroken counterfactual: value lost + the run built since.

        The reset day is itself an ACTIVE day (a reset row is only ever written
        on a submit), so its credit lives inside `run` and must not be dropped.
        `(today - local_date).days` dropped exactly that day, which is where the
        original off-by-one came from, and it additionally over-credits any day
        the user was not active. `run` is read from the ledger instead.
        """
        return self.from_value + self.run


# One round trip for what was three separate queries (most recent reset, the
# already-repaired check, the post-reset run). GET /v1/me/stats is one of the
# five concurrent calls in the Profile load (docs/ops-incident-report-july-2026),
# so its statement count is not free. Keeping it as ONE statement also keeps
# ONE code path: repair_streak and the /me/stats field both read this, so the
# advertised "Restore your N-day streak" can never drift from what a repair
# actually writes.
_RESTORABLE_SQL = text(
    """
    WITH last_reset AS (
        SELECT id, from_value, local_date
        FROM streak_events
        WHERE user_id = :uid AND event = 'reset' AND created_at >= :cutoff
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    )
    SELECT
        lr.id,
        lr.from_value,
        lr.local_date,
        (
            SELECT se.to_value FROM streak_events se
            WHERE se.user_id = :uid
              AND se.event IN ('extended', 'reset')
              AND se.local_date >= lr.local_date
            ORDER BY se.local_date DESC, se.id DESC
            LIMIT 1
        ) AS run,
        -- Anchored to THIS reset's id, not just the prefix: a user who
        -- repaired an EARLIER reset must not be disqualified from repairing
        -- this one. D-116(c) is why the anchor exists at all (streak_recon.py
        -- writes unanchored 'repaired' rows for timezone changes).
        EXISTS (
            SELECT 1 FROM streak_events se2
            WHERE se2.user_id = :uid
              AND se2.event = 'repaired'
              AND se2.note LIKE '%' || :prefix || lr.id::text || ']%'
        ) AS already_repaired
    FROM last_reset lr
    """,
)


async def _load_restorable(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: dt.datetime | None = None,
) -> RestorableReset | None:
    """The most recent `reset`, if it is inside the repair window and has not
    already been repaired. None otherwise.

    Filtering the window inside the LIMIT 1 is equivalent to "take the latest
    reset, then range-check it": an OLDER reset is by definition further
    outside the window, so it can never rescue a too-old latest one.
    """
    settings = get_settings()
    moment = now or dt.datetime.now(dt.UTC)
    cutoff = moment - dt.timedelta(hours=settings.STREAK_REPAIR_WINDOW_H)

    row = (
        await db.execute(
            _RESTORABLE_SQL,
            {"uid": user_id, "cutoff": cutoff, "prefix": _ANCHOR_PREFIX},
        )
    ).first()
    if row is None or row.already_repaired:
        return None
    return RestorableReset(
        reset_id=row.id,
        from_value=row.from_value,
        local_date=row.local_date,
        run=row.run,
    )


async def restorable_value(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: dt.datetime | None = None,
) -> int | None:
    """The streak value a repair would restore, or None if none is available.

    The unbroken counterfactual is "what the streak would read now if the gap
    had never happened": the value lost at the reset, PLUS the run built since
    it. The reset day itself is an ACTIVE day -- a reset row is only ever
    written on a submit -- so its credit is already inside the post-reset run
    and must not be dropped. `(today - reset.local_date).days` dropped exactly
    that day, which is where the original off-by-one came from.

    D-124: a repair that would not BEAT the current streak is not offered. The
    dashboard read "Restore your 1-day streak" to a user whose streak was
    already 1, which is a no-op dressed as a benefit. Worse than cosmetic: a
    reset is repairable at most once (D-116), so taking that offer would burn
    the user's only chance to repair it in exchange for nothing.
    """
    reset = await _load_restorable(db, user_id, now=now)
    if reset is None:
        return None
    stats = await db.get(UserStats, user_id)
    current = stats.current_streak if stats is not None else 0
    if reset.restores_to <= current:
        return None
    return reset.restores_to


async def repair_streak(
    db: AsyncSession,
    user: User,
    *,
    now: dt.datetime | None = None,
) -> dict:
    """Restore the streak value lost at the most recent repairable reset.

    The restored value comes entirely from the LEDGER (see
    RestorableReset.restores_to), never from current_streak, which submits made
    after the reset will have already mutated.
    """
    # D-104's lock class, applied to repair. The read of the restorable reset
    # and the write of the `repaired` row have nothing between them, and the
    # idempotency reservation is per-KEY, so two concurrent requests carrying
    # DIFFERENT Idempotency-Keys both miss the cache, both take their own
    # reservation, both see the same unrepaired reset, and both write a
    # repaired row -- restoring the streak twice. A per-(user, "streak_repair")
    # advisory lock serializes them, so the second observes the first's
    # committed anchor row and correctly 409s. Transaction-scoped, released on
    # commit/rollback, no explicit unlock.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_a), hashtext(:lock_b))"),
        {"lock_a": str(user.id), "lock_b": "streak_repair"},
    )

    reset = await _load_restorable(db, user.id, now=now)
    if reset is None:
        raise ApiError(
            409,
            "not_repairable",
            "There is no streak to restore right now.",
        )

    stats = await db.get(UserStats, user.id)
    if stats is None:
        raise ApiError(409, "not_repairable", "There is no streak to restore right now.")

    today = local_date_for(user.timezone, now=now)
    restored = reset.restores_to

    # D-124: refuse, do not merely hide. The stats payload stops ADVERTISING a
    # repair that would not beat the current streak, but a client that calls
    # this route anyway must not be allowed to spend the one-shot repair on a
    # no-op. Same 409 as every other non-repairable case, so it adds no new
    # failure mode for the client to handle.
    if restored <= stats.current_streak:
        raise ApiError(
            409,
            "not_repairable",
            "There is no streak to restore right now.",
        )

    before = stats.current_streak
    stats.current_streak = restored
    stats.longest_streak = max(stats.longest_streak, restored)
    db.add(
        StreakEvent(
            user_id=user.id,
            event="repaired",
            from_value=before,
            to_value=restored,
            local_date=today,
            note=(
                f"streak repaired within {get_settings().STREAK_REPAIR_WINDOW_H}h of the "
                f"reset on {reset.local_date.isoformat()} that lost {reset.from_value}; "
                f"restored {before} -> {restored} (lost {reset.from_value} plus the "
                f"{reset.run}-day run built since) {_anchor_marker(reset.reset_id)}"
            ),
        ),
    )
    await db.flush()
    return {"current_streak": restored, "repaired": True}
