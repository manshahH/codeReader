"""M5: resolves attempts stuck in status='grading_pending' by re-running
grade_rubric.

grading_failed is terminal (confirmed): this job only ever scans
status='grading_pending', so a row that already reached grading_failed --
either immediately at submit time (two invalid JSON responses) or here after
exhausting its retry budget -- is never re-picked.

attempts has no retry-count column (no migration needed for a purely
transient counter); the count is tracked inside attempt.grader_output as
{"_retry_count": n} while pending, the same "store transient state in the
existing JSONB column" pattern as D-34. It's cleared the moment the attempt
resolves either way, so it never reaches a client (grader_output is rebuilt
field-by-field from the resolved rubric result in attempts/service.py and
attempts/router.py, never dumped wholesale).

Idempotent: re-running against the same still-pending rows is safe -- each
row either resolves (graded/grading_failed) or has its retry count bumped by
exactly one, deterministically, per run.
"""

from __future__ import annotations

import datetime as dt
import decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.attempts.rubric import (
    RubricGradingInvalidResponse,
    RubricGradingTimeout,
    grade_rubric,
)
from app.attempts.service import update_concept_state, update_correctness_stats
from app.core import grader_health
from app.models import Attempt, Exercise, User

MAX_RETRY_ATTEMPTS = 3


async def _pending_attempts(db: AsyncSession, limit: int = 100) -> list[Attempt]:
    rows = await db.execute(
        select(Attempt).where(Attempt.status == "grading_pending").limit(limit),
    )
    return list(rows.scalars().all())


async def resolve_pending_summarize_grades(
    db: AsyncSession,
    redis=None,
    *,
    limit: int = 100,
) -> dict[str, int]:
    resolved = 0
    failed = 0
    still_pending = 0

    for attempt in await _pending_attempts(db, limit=limit):
        exercise = await db.scalar(
            select(Exercise).where(
                Exercise.id == attempt.exercise_id,
                Exercise.version == attempt.exercise_version,
            ),
        )
        user = await db.get(User, attempt.user_id)
        if exercise is None or user is None:
            # Orphaned row (exercise pulled, user deleted): leave it pending
            # rather than guess; a human/ops action resolves it explicitly.
            continue

        retry_count = int((attempt.grader_output or {}).get("_retry_count", 0))
        answer_text = attempt.answer.get("text", "")

        try:
            result = await grade_rubric(exercise, answer_text)
        except RubricGradingInvalidResponse:
            attempt.status = "grading_failed"
            attempt.grader_output = None
            failed += 1
            if redis is not None:
                await grader_health.mark_failure(redis)
            continue
        except RubricGradingTimeout:
            retry_count += 1
            if retry_count >= MAX_RETRY_ATTEMPTS:
                attempt.status = "grading_failed"
                attempt.grader_output = None
                failed += 1
            else:
                attempt.grader_output = {"_retry_count": retry_count}
                still_pending += 1
            if redis is not None:
                await grader_health.mark_failure(redis)
            continue

        now = dt.datetime.now(dt.UTC)
        attempt.status = "graded"
        attempt.is_correct = result.is_correct
        attempt.score = decimal.Decimal(str(result.score))
        attempt.grader_output = {
            "rubric_hits": result.rubric_hits,
            "rubric_misses": result.rubric_misses,
            "reference_answer": result.reference_answer,
        }
        attempt.graded_at = now
        resolved += 1
        if redis is not None:
            await grader_health.mark_success(redis)

        outcome = "correct" if result.is_correct else "incorrect"
        await update_concept_state(db, user, list(exercise.concepts), outcome, now)
        await update_correctness_stats(db, user, exercise.type, result.is_correct)

    await db.commit()
    return {"resolved": resolved, "failed": failed, "still_pending": still_pending}


async def _main() -> None:
    from redis.asyncio import Redis

    from app.config import get_settings
    from app.db import create_engine, create_session_factory

    engine = create_engine()
    redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        async with create_session_factory(engine)() as db:
            summary = await resolve_pending_summarize_grades(db, redis)
        print(f"grading_retry: {summary}")
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
