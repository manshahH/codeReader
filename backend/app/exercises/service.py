from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise


class ExerciseImmutableError(ValueError):
    pass


class ExerciseNotFoundError(LookupError):
    pass


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
        raise ExerciseImmutableError("live exercise versions are immutable")

    for field_name, value in values.items():
        setattr(exercise, field_name, value)
    await session.flush()
    return exercise
