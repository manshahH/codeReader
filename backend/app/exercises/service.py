from __future__ import annotations

import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise


class ExerciseImmutableError(ValueError):
    pass


class ExerciseNotFoundError(LookupError):
    pass


# D-58: D-5's immutability is about CONTENT -- what the user saw and how it
# was graded can never change under a (id, version). Operational state is not
# content: a live row must be able to leave circulation (the docs/00 kill
# risk is "a wrong answer on the HN front page", mitigated by fast pull).
LIVE_MUTABLE_FIELDS = frozenset({"status"})
LIVE_STATUS_TRANSITIONS = frozenset({"pulled", "retired"})


async def update_exercise_fields(
    session: AsyncSession,
    exercise_id: uuid.UUID,
    version: int,
    values: dict[str, Any],
) -> Exercise:
    exercise = await session.scalar(
        select(Exercise).where(Exercise.id == exercise_id, Exercise.version == version),
    )
    if exercise is None:
        raise ExerciseNotFoundError(f"exercise {exercise_id} v{version} not found")
    if exercise.status == "live":
        content_fields = sorted(set(values) - LIVE_MUTABLE_FIELDS)
        if content_fields:
            raise ExerciseImmutableError(
                f"live exercise content is immutable; refused fields: {content_fields}",
            )
        new_status = values.get("status")
        if new_status is not None and new_status not in LIVE_STATUS_TRANSITIONS:
            raise ExerciseImmutableError(
                f"a live exercise can only move to {sorted(LIVE_STATUS_TRANSITIONS)},"
                f" not {new_status!r}",
            )

    for field_name, value in values.items():
        setattr(exercise, field_name, value)
    await session.flush()
    return exercise


async def pull_exercise(
    session: AsyncSession,
    redis: Redis,
    exercise_id: uuid.UUID,
    version: int,
) -> tuple[Exercise, int]:
    """Incident path: take a bad live exercise out of circulation NOW (D-58).

    Sets status='pulled' and purges every still-servable daily session (DB
    row + Redis cache key) that references the exercise, so affected users
    resample a clean session on their next fetch instead of being served the
    bad exercise from cache for up to 36 hours. Returns the exercise and how
    many user sessions were purged. Commits (inside the purge, which needs
    the status flip and the row deletions in one transaction): pulling is an
    incident action, not a step in a larger transaction.
    """
    from app.sessions.service import purge_sessions_referencing

    exercise = await update_exercise_fields(session, exercise_id, version, {"status": "pulled"})
    purged = await purge_sessions_referencing(session, redis, exercise_id)
    return exercise, purged
