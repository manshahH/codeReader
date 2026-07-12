from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.core.errors import ApiError
from app.models import User
from app.reviews.service import get_review_status, upsert_review
from app.schemas.reviews import ReviewRequest, ReviewResponse, ReviewStatusResponse

router = APIRouter(prefix="/v1", tags=["reviews"])


@router.post("/me/review", response_model=ReviewResponse)
async def post_review(
    payload: ReviewRequest,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> ReviewResponse:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    return await upsert_review(session, user, payload)


@router.get("/me/review", response_model=ReviewStatusResponse)
async def get_review(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> ReviewStatusResponse:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    return await get_review_status(session, user)
