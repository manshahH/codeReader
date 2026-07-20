from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.auth.service import user_response
from app.core.errors import ApiError
from app.email.deliveries import email_preferences
from app.models import User
from app.schemas.users import AccuracyHistoryDay, ActivityDay, MeSessionSummary, UpdateMeRequest
from app.users.service import (
    get_accuracy_history,
    get_activity,
    get_concepts,
    get_sessions,
    get_stats,
    update_me,
)

router = APIRouter(prefix="/v1", tags=["users"])


@router.get("/me")
async def me(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> dict[str, object]:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    return {
        "user": user_response(user, email_prefs=await email_preferences(session, user.id)),
    }


@router.patch("/me")
async def patch_me(
    payload: UpdateMeRequest,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> dict[str, object]:
    updates = payload.model_dump(exclude_unset=True)
    user = await update_me(session, current_user.id, updates)
    return {
        "user": user_response(user, email_prefs=await email_preferences(session, user.id)),
    }


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


@router.get("/me/activity", response_model=list[ActivityDay])
async def me_activity(
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> list[dict[str, object]]:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    return await get_activity(session, user, date_from=date_from, date_to=date_to)


@router.get("/me/sessions", response_model=list[MeSessionSummary])
async def me_sessions(
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> list[dict[str, object]]:
    return await get_sessions(session, current_user.id, limit=limit)


@router.get("/me/accuracy-history", response_model=list[AccuracyHistoryDay])
async def me_accuracy_history(
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> list[dict[str, object]]:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    return await get_accuracy_history(session, user, date_from=date_from, date_to=date_to)