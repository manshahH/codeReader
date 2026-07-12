"""Periodic job: computes exercise_stats from attempts.

The ONLY place attempts are aggregated. GET /me/stats, /me/concepts, and the
percentile field on POST /attempts all read the precomputed exercise_stats /
user_stats / user_concept_state tables, never GROUP BY attempts live.

D-61: also the only writer of exercises.difficulty_empirical -- a linear
map of solve_rate onto the 1-10 difficulty scale (solve_rate 1.0 -> 1.0,
solve_rate 0.0 -> 10.0), written once an exercise version has >=
MIN_EMPIRICAL_N graded attempts. It is derived operational data, not
content, so writing it does not touch D-5's content-immutability (D-58).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExerciseStat
from app.sessions.sampler import MIN_EMPIRICAL_N


async def compute_exercise_stats(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            text(
                """
                -- D-8 was corrected (see docs/07): idempotency is Redis-only,
                -- and a replay racing a Redis outage/loss CAN duplicate an
                -- attempts row for the same (user, exercise, session_date).
                -- Collapse to one row per that key -- the earliest-created
                -- graded attempt -- before counting, so a duplicate never
                -- inflates a percentile's n or its solve rate.
                WITH deduped AS (
                    SELECT DISTINCT ON (user_id, exercise_id, exercise_version, session_date)
                        exercise_id,
                        exercise_version,
                        is_correct,
                        time_taken_ms
                    FROM attempts
                    WHERE status = 'graded'
                    ORDER BY user_id, exercise_id, exercise_version, session_date, created_at ASC
                )
                SELECT
                    exercise_id,
                    exercise_version,
                    count(*) AS attempts_count,
                    count(*) FILTER (WHERE is_correct) AS correct_count,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY time_taken_ms) AS median_time_ms
                FROM deduped
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

    await session.execute(
        text(
            """
            UPDATE exercises e
            SET difficulty_empirical = least(
                10, greatest(1, round((1 + 9 * (1 - s.solve_rate))::numeric, 2))
            )
            FROM exercise_stats s
            WHERE s.exercise_id = e.id
              AND s.exercise_version = e.version
              AND s.attempts_count >= :min_n
              AND s.solve_rate IS NOT NULL
            """,
        ),
        {"min_n": MIN_EMPIRICAL_N},
    )

    await session.commit()
    return len(rows)


async def _main() -> None:
    from app.db import create_engine, create_session_factory

    engine = create_engine()
    try:
        async with create_session_factory(engine)() as session:
            count = await compute_exercise_stats(session)
        print(f"percentiles: computed stats for {count} (exercise, version) pairs")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
