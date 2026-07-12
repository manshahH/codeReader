from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.attempts.service import get_attempt, submit_attempt
from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.core.errors import ApiError
from app.core.metrics import record_outcome
from app.core.redis import get_redis
from app.models import User
from app.schemas.attempts import AttemptRequest

router = APIRouter(prefix="/v1", tags=["attempts"])
RedisDep = Depends(get_redis)


@router.post("/attempts")
async def post_attempt(
    payload: AttemptRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
) -> JSONResponse:
    if not idempotency_key:
        raise ApiError(400, "validation_error", "Idempotency-Key header is required.")

    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")

    try:
        outcome = await submit_attempt(
            session,
            redis,
            user,
            idempotency_key=idempotency_key,
            payload=payload,
        )
    except ApiError:
        # Expected control flow (already_attempted, rate_limited, ...), not
        # an insert failure -- still counts toward the denominator, not the
        # numerator, of the attempt-insert error rate (docs/06 M7 golden
        # signal).
        await record_outcome(redis, "attempt_insert", is_error=False)
        raise
    except Exception:
        await record_outcome(redis, "attempt_insert", is_error=True)
        raise
    else:
        await record_outcome(redis, "attempt_insert", is_error=False)

    headers = dict(outcome.rate_limit_headers or {})
    if outcome.is_replay:
        headers["X-Idempotent-Replay"] = "true"
    return JSONResponse(content=outcome.body, status_code=outcome.status_code, headers=headers)


@router.get("/attempts/{attempt_id}")
async def get_attempt_by_id(
    attempt_id: int,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> dict:
    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")

    body = await get_attempt(session, user, attempt_id)
    if body is None:
        raise ApiError(404, "not_found", "Attempt not found.")
    headers = {"Retry-After": "3"} if body["status"] == "grading_pending" else {}
    return JSONResponse(content=body, status_code=200, headers=headers)
