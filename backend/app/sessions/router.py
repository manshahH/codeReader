from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.core.errors import ApiError
from app.core.metrics import record_latency
from app.core.redis import get_redis
from app.models import User
from app.schemas.session import SessionReviewResponse
from app.sessions.service import get_today_review, get_today_session

router = APIRouter(prefix="/v1", tags=["sessions"])
RedisDep = Depends(get_redis)


@router.get("/session/today")
async def session_today(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
) -> dict:
    started = time.perf_counter()
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    try:
        return await get_today_session(session, redis, user)
    finally:
        # One of the two non-negotiable golden signals (docs/06 M7): a
        # climbing session-fetch p95 is an early incident signal.
        await record_latency(redis, "session_fetch", (time.perf_counter() - started) * 1000)


@router.get("/session/today/review", response_model=SessionReviewResponse)
async def session_today_review(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
) -> dict:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    return await get_today_review(session, redis, user)
