"""Periodic job: computes exercise_stats from attempts.

The ONLY place attempts are aggregated. GET /me/stats, /me/concepts, and the
percentile field on POST /attempts all read the precomputed exercise_stats /
user_stats / user_concept_state tables, never GROUP BY attempts live.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExerciseStat


async def compute_exercise_stats(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            text(
                """
                SELECT
                    exercise_id,
                    exercise_version,
                    count(*) AS attempts_count,
                    count(*) FILTER (WHERE is_correct) AS correct_count,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY time_taken_ms) AS median_time_ms
                FROM attempts
                WHERE status = 'graded'
                GROUP BY exercise_id, exercise_version
                """,
            ),
        )
    ).all()

    for row in rows:
        solve_rate = (row.correct_count / row.attempts_count) if row.attempts_count else None
        stmt = insert(ExerciseStat).values(
            exercise_id=row.exercise_id,
            exercise_version=row.exercise_version,
            attempts_count=row.attempts_count,
            correct_count=row.correct_count,
            solve_rate=solve_rate,
            median_time_ms=int(row.median_time_ms) if row.median_time_ms is not None else None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ExerciseStat.exercise_id, ExerciseStat.exercise_version],
            set_={
                "attempts_count": stmt.excluded.attempts_count,
                "correct_count": stmt.excluded.correct_count,
                "solve_rate": stmt.excluded.solve_rate,
                "median_time_ms": stmt.excluded.median_time_ms,
                "computed_at": text("now()"),
            },
        )
        await session.execute(stmt)

    await session.commit()
    return len(rows)
