from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.auth.service import user_response
from app.core.errors import ApiError
from app.models import User
from app.schemas.users import UpdateMeRequest
from app.users.service import get_concepts, get_stats, update_me

router = APIRouter(prefix="/v1", tags=["users"])


@router.get("/me")
async def me(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> dict[str, object]:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    return {"user": user_response(user)}


@router.patch("/me")
async def patch_me(
    payload: UpdateMeRequest,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> dict[str, object]:
    updates = payload.model_dump(exclude_unset=True)
    user = await update_me(session, current_user.id, updates)
    return {"user": user_response(user)}


@router.get("/me/stats")
async def me_stats(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> dict[str, object]:
    return await get_stats(session, current_user.id)


@router.get("/me/concepts")
async def me_concepts(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> list[dict[str, object]]:
    return await get_concepts(session, current_user.id)