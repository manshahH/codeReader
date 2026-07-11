from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.core.errors import ApiError
from app.disputes.service import create_dispute
from app.models import User
from app.schemas.disputes import DisputeRequest, DisputeResponse

router = APIRouter(prefix="/v1", tags=["disputes"])


@router.post(
    "/exercises/{exercise_id}/v/{version}/dispute",
    status_code=201,
    response_model=DisputeResponse,
)
async def post_dispute(
    exercise_id: uuid.UUID,
    version: int,
    payload: DisputeRequest,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> DisputeResponse:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")

    return await create_dispute(
        session,
        user,
        exercise_id=exercise_id,
        version=version,
        payload=payload,
    )
