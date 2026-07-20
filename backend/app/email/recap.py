"""What actually happened in a user's week (A3, D-137(8)).

Every number here is DERIVED from tables that already exist. No counter was
added for the recap, which is a constraint worth stating because the cheap move
would have been a weekly rollup table, and a rollup is a second source of truth
that can disagree with the attempts it summarises.

Everything buckets on `session_date`, the user-LOCAL date an attempt counted
toward. That is the same field the streak, the activity grid and the accuracy
history already bucket on, so a week in the recap is the same week the user sees
everywhere else in the product. Deriving from `created_at` instead would put a
late-evening attempt in a different week than the dashboard shows it in.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from collections import Counter

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attempt, DailySession, Exercise, UserStats

# How many concepts the recap names. A recap that lists twenty concepts is a
# data dump; the point is a couple of things the reader recognises.
MAX_CONCEPTS = 4


@dataclasses.dataclass(frozen=True)
class WeeklyRecap:
    week_start: dt.date
    week_end: dt.date
    sessions_completed: int
    exercises_attempted: int
    correct: int
    graded: int
    concepts: list[str]
    current_streak: int
    longest_streak: int

    @property
    def accuracy_pct(self) -> int | None:
        """None when nothing resolved, NOT 0. A week of only pending grades is
        not a 0% week, and rendering it as one would be a false statement about
        the reader's performance."""
        if self.graded == 0:
            return None
        return round(100 * self.correct / self.graded)

    @property
    def is_empty(self) -> bool:
        """An empty week is not sent at all (D-137(8)). A report of nothing is
        not a report, and "here is your week: nothing" is guilt copy however it
        is worded, which docs/10 rules out."""
        return self.exercises_attempted == 0


def week_bounds(local_date: dt.date) -> tuple[dt.date, dt.date]:
    """The Monday..Sunday ISO week that ENDED before `local_date`.

    The recap runs on a Monday and reports the week just finished, so this
    deliberately looks BACKWARD past the current (partial) week. Reporting the
    in-progress week would send a Monday-morning summary of Monday morning.
    """
    this_monday = local_date - dt.timedelta(days=local_date.weekday())
    last_monday = this_monday - dt.timedelta(days=7)
    return last_monday, last_monday + dt.timedelta(days=6)


async def build_weekly_recap(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    week_start: dt.date,
    week_end: dt.date,
) -> WeeklyRecap:
    sessions_completed = (
        await session.scalar(
            select(func.count())
            .select_from(DailySession)
            .where(
                DailySession.user_id == user_id,
                DailySession.session_date >= week_start,
                DailySession.session_date <= week_end,
                DailySession.completed_at.is_not(None),
            ),
        )
    ) or 0

    # One pass for all three attempt numbers. `graded` is the accuracy
    # DENOMINATOR and counts only rows where is_correct actually resolved: a
    # pending rubric grade and a skip (D-93) must not be counted as wrong.
    # `exercises_attempted` counts every submission regardless of status,
    # matching D-38's rule that a submission counts as attempted.
    totals = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(case((Attempt.is_correct.is_not(None), 1), else_=0)), 0
                ).cast(Integer),
                func.coalesce(func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)), 0).cast(
                    Integer
                ),
            ).where(
                Attempt.user_id == user_id,
                Attempt.session_date >= week_start,
                Attempt.session_date <= week_end,
            ),
        )
    ).one()
    exercises_attempted, graded, correct = int(totals[0]), int(totals[1]), int(totals[2])

    # "Concepts improved" is reported as "concepts you got right", and the
    # rename is the honest part (D-137(8)). user_concept_state.mastery is a
    # CURRENT SNAPSHOT with no history, so a real week-over-week delta is not
    # derivable from existing tables; manufacturing one means storing a weekly
    # mastery sample, which is the new counter this is not allowed to add. So
    # the recap says the thing that IS true.
    #
    # Aggregated in Python rather than with unnest + GROUP BY. A week is at
    # most a few dozen rows for one user, so the SQL buys nothing measurable,
    # and array-unnest-with-grouping is the kind of expression that is easy to
    # write subtly wrong and hard to read later.
    concept_arrays = await session.scalars(
        select(Exercise.concepts)
        .select_from(Attempt)
        .join(
            Exercise,
            (Exercise.id == Attempt.exercise_id) & (Exercise.version == Attempt.exercise_version),
        )
        .where(
            Attempt.user_id == user_id,
            Attempt.session_date >= week_start,
            Attempt.session_date <= week_end,
            Attempt.is_correct.is_(True),
        ),
    )
    hits: Counter[str] = Counter()
    for array in concept_arrays.all():
        hits.update(array or ())
    # Sorted by frequency then name, so the same week always renders the same
    # list. Counter.most_common alone leaves ties in insertion order, which
    # would make the mail non-deterministic for no reason.
    concepts = [
        concept for concept, _ in sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:MAX_CONCEPTS]

    stats = await session.get(UserStats, user_id)

    return WeeklyRecap(
        week_start=week_start,
        week_end=week_end,
        sessions_completed=int(sessions_completed),
        exercises_attempted=exercises_attempted,
        correct=correct,
        graded=graded,
        concepts=concepts,
        current_streak=stats.current_streak if stats else 0,
        longest_streak=stats.longest_streak if stats else 0,
    )
