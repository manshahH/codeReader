"""POST /exercises/{id}/v/{version}/dispute (docs/05 section 6).

One open dispute per (user, exercise, version); pulling the exercise stays a
manual admin action at MVP (docs/03) -- this only records the report and
fires the operator alert event.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.events import alert_dispute_opened
from app.models import Dispute, Exercise, User
from app.schemas.disputes import DisputeRequest, DisputeResponse


async def create_dispute(
    db: AsyncSession,
    user: User,
    *,
    exercise_id: uuid.UUID,
    version: int,
    payload: DisputeRequest,
) -> DisputeResponse:
    exercise = await db.scalar(
        select(Exercise).where(Exercise.id == exercise_id, Exercise.version == version),
    )
    if exercise is None:
        raise ApiError(404, "not_found", "Exercise not found.")

    existing_open = await db.scalar(
        select(Dispute.id).where(
            Dispute.user_id == user.id,
            Dispute.exercise_id == exercise_id,
            Dispute.exercise_version == version,
            Dispute.status == "open",
        ),
    )
    if existing_open is not None:
        raise ApiError(
            409,
            "idempotency_conflict",
            "You already have an open dispute for this exercise version.",
        )

    dispute = Dispute(
        exercise_id=exercise_id,
        exercise_version=version,
        user_id=user.id,
        attempt_id=payload.attempt_id,
        reason=payload.reason,
        body=payload.body,
    )
    db.add(dispute)
    await db.flush()
    await db.commit()

    alert_dispute_opened(
        dispute_id=dispute.id,
        exercise_id=exercise_id,
        exercise_version=version,
        user_id=user.id,
        reason=payload.reason,
    )

    return DisputeResponse(dispute_id=dispute.id, status=dispute.status)
