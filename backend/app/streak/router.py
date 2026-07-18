"""POST /v1/streak/repair (A1 streak safety net, docs/10; D-116).

Idempotency reuses the attempts discipline verbatim (core/idempotency.py) in
its own `streak_repair` namespace: SET NX reservation, 24h cached record,
byte-identical replay of the stored body. The two acceptance rules docs/10
states are reconciled the same way attempts reconciles them -- a replay of the
SAME Idempotency-Key returns the cached success, while a genuinely new request
against an already-repaired or out-of-window reset is a 409. Only successes are
cached: a 409 is a statement about current state, not a recorded outcome, so it
must stay live.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.core.errors import ApiError
from app.core.idempotency import (
    acquire_reservation,
    get_cached,
    release_reservation,
    request_hash,
    wait_for_cached,
)
from app.core.idempotency import store as store_idempotency
from app.core.redis import get_redis
from app.models import User
from app.streak.service import IDEMPOTENCY_NAMESPACE, repair_streak

router = APIRouter(prefix="/v1", tags=["streak"])
RedisDep = Depends(get_redis)

_WAIT_TIMEOUT_SECONDS = 5.0


@router.post("/streak/repair")
async def streak_repair(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
) -> dict[str, object]:
    if not idempotency_key:
        raise ApiError(400, "validation_error", "Idempotency-Key header is required.")

    user = await session.get(User, current_user.id)
    if user is None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")

    # The request carries no body, so the hash is over the identity of the
    # actor. That still makes a key reused across two users a conflict rather
    # than one user replaying the other's cached result.
    req_hash = request_hash({"user_id": str(user.id)})

    cached = await get_cached(
        redis,
        namespace=IDEMPOTENCY_NAMESPACE,
        idempotency_key=idempotency_key,
    )
    if cached is not None:
        if cached.request_hash != req_hash:
            raise ApiError(
                409,
                "idempotency_conflict",
                "This Idempotency-Key was already used with a different request body.",
            )
        return cached.body

    reserved = await acquire_reservation(
        redis,
        namespace=IDEMPOTENCY_NAMESPACE,
        idempotency_key=idempotency_key,
    )
    if not reserved:
        record = await wait_for_cached(
            redis,
            namespace=IDEMPOTENCY_NAMESPACE,
            idempotency_key=idempotency_key,
            timeout_seconds=_WAIT_TIMEOUT_SECONDS,
        )
        if record is not None:
            if record.request_hash != req_hash:
                raise ApiError(
                    409,
                    "idempotency_conflict",
                    "This Idempotency-Key was already used with a different request body.",
                )
            return record.body

    try:
        body = await repair_streak(session, user)
        await session.commit()
        await store_idempotency(
            redis,
            namespace=IDEMPOTENCY_NAMESPACE,
            idempotency_key=idempotency_key,
            request_hash=req_hash,
            status_code=200,
            body=body,
        )
        return body
    finally:
        await release_reservation(
            redis,
            namespace=IDEMPOTENCY_NAMESPACE,
            idempotency_key=idempotency_key,
        )
