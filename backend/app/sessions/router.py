from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.core.errors import ApiError
from app.core.redis import get_redis
from app.models import User
from app.sessions.service import get_today_session

router = APIRouter(prefix="/v1", tags=["sessions"])
RedisDep = Depends(get_redis)


@router.get("/session/today")
async def session_today(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
) -> dict:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    return await get_today_session(session, redis, user)
