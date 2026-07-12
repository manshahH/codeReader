"""GET /me/stats, GET /me/concepts, GET /me/sessions, GET /me/accuracy-history,
PATCH /me (docs/05 section 3).

The stats/concepts reads are straight reads of the precomputed
user_stats / user_concept_state tables -- never aggregates attempts at
request time. get_sessions/get_accuracy_history are the two exceptions:
there is no precomputed table for "per-session summary" or "daily accuracy
trend", so these do aggregate attempts directly, at request time, same as
get_activity already does for daily_sessions.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections import defaultdict

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.accuracy import project as project_accuracy
from app.core.errors import ApiError
from app.core.timezones import local_date_for
from app.jobs.streak_recon import reconcile_streak_for_timezone_change
from app.models import Attempt, DailySession, Exercise, User, UserConceptState, UserStats

ACTIVITY_DEFAULT_WINDOW_DAYS = 365
ACCURACY_HISTORY_DEFAULT_WINDOW_DAYS = 90


async def get_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    total_sessions = await db.scalar(
        select(func.count())
        .select_from(DailySession)
        .where(DailySession.user_id == user_id, DailySession.completed_at.isnot(None)),
    )
    stats = await db.get(UserStats, user_id)
    if stats is None:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "streak_freezes": 0,
            "total_attempts": 0,
            "total_correct": 0,
            "accuracy_by_type": {},
            "last_active_local_date": None,
            "total_sessions": total_sessions or 0,
        }
    return {
        "current_streak": stats.current_streak,
        "longest_streak": stats.longest_streak,
        "streak_freezes": stats.streak_freezes,
        "total_attempts": stats.total_attempts,
        "total_correct": stats.total_correct,
        "accuracy_by_type": project_accuracy(stats.accuracy_by_type),
        "last_active_local_date": (
            stats.last_active_local_date.isoformat() if stats.last_active_local_date else None
        ),
        "total_sessions": total_sessions or 0,
    }


async def get_concepts(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = await db.execute(
        select(UserConceptState)
        .where(UserConceptState.user_id == user_id)
        .order_by(UserConceptState.mastery.asc()),
    )
    return [
        {
            "concept": row.concept,
            "mastery": float(row.mastery),
            "attempts": row.attempts,
            "next_review_at": row.next_review_at.isoformat() if row.next_review_at else None,
        }
        for row in rows.scalars().all()
    ]


async def get_activity(
    db: AsyncSession,
    user: User,
    *,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list[dict]:
    """The contribution-grid data (D-93a): one entry per row already present
    in daily_sessions -- a row is written the first time a user opens the app
    that day (D-17/D-23), and completed_at distinguishes finished vs.
    opened-but-not-finished. Default window: the 365 days ending today in the
    user's own local timezone, same "today" every other date-sensitive read
    in this app (sessions, streaks) already uses.
    """
    end = date_to or local_date_for(user.timezone)
    start = date_from or (end - dt.timedelta(days=ACTIVITY_DEFAULT_WINDOW_DAYS - 1))

    rows = await db.execute(
        select(DailySession.session_date, DailySession.completed_at)
        .where(
            DailySession.user_id == user.id,
            DailySession.session_date >= start,
            DailySession.session_date <= end,
        )
        .order_by(DailySession.session_date.asc()),
    )
    return [
        {"session_date": session_date.isoformat(), "completed": completed_at is not None}
        for session_date, completed_at in rows.all()
    ]


async def get_sessions(db: AsyncSession, user_id: uuid.UUID, *, limit: int) -> list[dict]:
    """GET /me/sessions: the most recent daily_sessions rows, each joined
    against that day's attempts for correct/skipped counts and against
    exercises for the concepts the (whole, not just attempted) session
    covers. Batched, not N+1: one query for the sessions, one for every
    exercise any of them references, one for every attempt on any of their
    session_dates.
    """
    session_rows = await db.execute(
        select(DailySession)
        .where(DailySession.user_id == user_id)
        .order_by(DailySession.session_date.desc())
        .limit(limit),
    )
    sessions = session_rows.scalars().all()
    if not sessions:
        return []

    exercise_keys = {
        (uuid.UUID(item["exercise_id"]), item["version"])
        for daily_session in sessions
        for item in daily_session.exercise_list
    }
    concepts_by_key: dict[tuple[uuid.UUID, int], list[str]] = {}
    if exercise_keys:
        exercise_rows = await db.execute(
            select(Exercise.id, Exercise.version, Exercise.concepts).where(
                tuple_(Exercise.id, Exercise.version).in_(exercise_keys),
            ),
        )
        concepts_by_key = {
            (ex_id, version): list(concepts)
            for ex_id, version, concepts in exercise_rows.all()
        }

    dates = [daily_session.session_date for daily_session in sessions]
    attempt_rows = await db.execute(
        select(Attempt.session_date, Attempt.is_correct, Attempt.status).where(
            Attempt.user_id == user_id,
            Attempt.session_date.in_(dates),
        ),
    )
    correct_by_date: dict[dt.date, int] = defaultdict(int)
    skipped_by_date: dict[dt.date, int] = defaultdict(int)
    for session_date, is_correct, status in attempt_rows.all():
        if status == "skipped":
            skipped_by_date[session_date] += 1
        elif is_correct:
            correct_by_date[session_date] += 1

    result = []
    for daily_session in sessions:
        concepts: set[str] = set()
        for item in daily_session.exercise_list:
            key = (uuid.UUID(item["exercise_id"]), item["version"])
            concepts.update(concepts_by_key.get(key, []))
        result.append(
            {
                "session_date": daily_session.session_date.isoformat(),
                "completed": daily_session.completed_at is not None,
                "exercise_count": len(daily_session.exercise_list),
                "correct_count": correct_by_date.get(daily_session.session_date, 0),
                "skipped_count": skipped_by_date.get(daily_session.session_date, 0),
                "concepts": sorted(concepts),
            },
        )
    return result


async def get_accuracy_history(
    db: AsyncSession,
    user: User,
    *,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list[dict]:
    """GET /me/accuracy-history: a daily correct/total ratio for the
    "average accuracy over time" trend line. Bucketed by
    attempts.session_date (the app's existing local-day field, already
    correct per-user at submit time) rather than re-deriving a day boundary
    from created_at. Only days with at least one deterministically-resolved
    attempt (is_correct IS NOT NULL) appear -- a skip or a still-pending
    grade contributes to neither the numerator nor the denominator.
    """
    end = date_to or local_date_for(user.timezone)
    start = date_from or (end - dt.timedelta(days=ACCURACY_HISTORY_DEFAULT_WINDOW_DAYS - 1))

    rows = await db.execute(
        select(Attempt.session_date, Attempt.is_correct)
        .where(
            Attempt.user_id == user.id,
            Attempt.session_date >= start,
            Attempt.session_date <= end,
            Attempt.is_correct.isnot(None),
        )
        .order_by(Attempt.session_date.asc()),
    )
    totals: dict[dt.date, list[int]] = defaultdict(lambda: [0, 0])  # [correct, total]
    for session_date, is_correct in rows.all():
        bucket = totals[session_date]
        bucket[1] += 1
        if is_correct:
            bucket[0] += 1

    return [
        {"date": day.isoformat(), "accuracy": correct / total, "attempts": total}
        for day, (correct, total) in sorted(totals.items())
    ]


async def update_me(db: AsyncSession, user_id: uuid.UUID, updates: dict) -> User:
    """Applies only the fields the client actually sent (docs/05: all optional).

    Setting `level` is the onboarding action itself (docs/03: onboarding is
    "level pick, one screen") -- there is no separate "mark onboarded" call.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")

    if "display_name" in updates:
        user.display_name = updates["display_name"]
    if "timezone" in updates:
        # Must run BEFORE reassigning user.timezone: it compares the new
        # zone's "today" against the stats row recorded under the current
        # (about to be old) one (D-64).
        await reconcile_streak_for_timezone_change(db, user, updates["timezone"])
        user.timezone = updates["timezone"]
    if "level" in updates:
        user.level = updates["level"]
        user.onboarded = True
    if "reminder_local_time" in updates:
        value = updates["reminder_local_time"]
        user.reminder_local_time = dt.time.fromisoformat(value) if value else None

    await db.flush()
    await db.commit()
    return user
