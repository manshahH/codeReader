"""GET /admin/metrics: the four golden signals from docs/02, minimally.

session_fetch_p95_ms and attempt_insert_error_rate come from the Redis
counters recorded in sessions/router.py and attempts/router.py
(app.core.metrics). pending_grade_count and dispute_rate_by_exercise are the
two non-negotiable signals (docs/06 M7): a climbing pending-grade count
means the grader is failing; a spiking dispute rate on one exercise means a
bad answer key is live. Both are computed directly from the DB -- this is an
ops-only, low-QPS endpoint, not the user-facing "never aggregate attempts at
request time" path docs/04 protects.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import error_rate, p95_latency_ms
from app.jobs.runner import JobScheduler
from app.models import Review, ReviewHistory

DISPUTE_RATE_LIMIT = 20


async def pending_grade_count(db: AsyncSession) -> int:
    result = await db.execute(
        text("SELECT count(*) FROM attempts WHERE status = 'grading_pending'"),
    )
    return int(result.scalar_one())


async def dispute_rate_by_exercise(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            text(
                """
                SELECT
                    d.exercise_id,
                    d.exercise_version,
                    count(*) FILTER (WHERE d.status = 'open') AS open_disputes,
                    coalesce(s.attempts_count, 0) AS graded_attempts
                FROM disputes d
                LEFT JOIN exercise_stats s
                    ON s.exercise_id = d.exercise_id
                   AND s.exercise_version = d.exercise_version
                GROUP BY d.exercise_id, d.exercise_version, s.attempts_count
                HAVING count(*) FILTER (WHERE d.status = 'open') > 0
                ORDER BY count(*) FILTER (WHERE d.status = 'open') DESC
                LIMIT :limit
                """,
            ),
            {"limit": DISPUTE_RATE_LIMIT},
        )
    ).all()
    results = []
    for row in rows:
        rate = (row.open_disputes / row.graded_attempts) if row.graded_attempts else None
        results.append(
            {
                "exercise_id": str(row.exercise_id),
                "exercise_version": row.exercise_version,
                "open_disputes": row.open_disputes,
                "graded_attempts": row.graded_attempts,
                "dispute_rate": rate,
            },
        )
    return results


def job_health(scheduler: JobScheduler | None) -> dict[str, dict[str, Any]] | None:
    """M8 beta readiness: "job-runner health" -- is grading_retry/percentiles/
    partitions still ticking, and when did each last succeed/fail. None (not
    an empty dict) when jobs are disabled (JOBS_ENABLED=false), so the
    /admin/metrics response distinguishes "no scheduler running" from "a
    scheduler running with zero jobs", which should never happen in
    practice but should be visibly distinct from a config error if it did.
    """
    if scheduler is None:
        return None
    return {
        name: {
            "run_count": scheduler.run_counts[name],
            "error_count": scheduler.error_counts[name],
            "last_run_at": scheduler.last_run_at[name],
            "last_error_at": scheduler.last_error_at[name],
        }
        for name in scheduler.run_counts
    }


async def compute_retention(
    db: AsyncSession,
    cohort_start: dt.date,
    offset_days: int,
) -> dict[str, Any]:
    """D1/D7 retention (CLAUDE.md M8 part 3): of the users whose session was
    fetched/built on `cohort_start`, how many came back `offset_days` later.
    Uses daily_sessions (a row is written the first time a user opens the
    app that day, D-17/D-23) as the activity signal rather than attempts --
    simple and already durable, and "did they come back" is about opening
    the app, not necessarily finishing every exercise.
    """
    return_date = cohort_start + dt.timedelta(days=offset_days)
    row = (
        await db.execute(
            text(
                """
                WITH cohort AS (
                    SELECT DISTINCT user_id FROM daily_sessions WHERE session_date = :cohort_start
                ), returned AS (
                    SELECT DISTINCT ds.user_id
                    FROM daily_sessions ds
                    JOIN cohort c ON c.user_id = ds.user_id
                    WHERE ds.session_date = :return_date
                )
                SELECT
                    (SELECT count(*) FROM cohort) AS cohort_size,
                    (SELECT count(*) FROM returned) AS returned_count
                """,
            ),
            {"cohort_start": cohort_start, "return_date": return_date},
        )
    ).one()
    cohort_size = row.cohort_size
    returned_count = row.returned_count
    return {
        "cohort_start": cohort_start.isoformat(),
        "return_date": return_date.isoformat(),
        "offset_days": offset_days,
        "cohort_size": cohort_size,
        "returned_count": returned_count,
        "retention_rate": (returned_count / cohort_size) if cohort_size else None,
    }


async def list_reviews(db: AsyncSession) -> list[dict[str, Any]]:
    reviews = (
        (await db.execute(select(Review).order_by(Review.created_at.desc()))).scalars().all()
    )
    history_rows = (
        (await db.execute(select(ReviewHistory).order_by(ReviewHistory.created_at.asc())))
        .scalars()
        .all()
    )
    history_by_user: dict[Any, list[dict[str, Any]]] = {}
    for row in history_rows:
        history_by_user.setdefault(row.user_id, []).append(
            {
                "rating": row.rating,
                "body": row.body,
                "created_at": row.created_at.isoformat(),
            },
        )
    return [
        {
            "user_id": str(review.user_id),
            "rating": review.rating,
            "body": review.body,
            "created_at": review.created_at.isoformat(),
            "updated_at": review.updated_at.isoformat(),
            "history": history_by_user.get(review.user_id, []),
        }
        for review in reviews
    ]


async def collect_metrics(
    db: AsyncSession,
    redis: Redis,
    job_scheduler: JobScheduler | None = None,
) -> dict:
    return {
        "session_fetch_p95_ms": await p95_latency_ms(redis, "session_fetch"),
        "attempt_insert_error_rate": await error_rate(redis, "attempt_insert"),
        "pending_grade_count": await pending_grade_count(db),
        "dispute_rate_by_exercise": await dispute_rate_by_exercise(db),
        "empty_session_rate": await error_rate(redis, "session_build"),
        "jobs": job_health(job_scheduler),
    }
