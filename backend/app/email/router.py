"""Email capture routes (A2, D-120; docs/05 section 3).

Deliberately NOT folded into PATCH /me. PATCH /me is a partial update: it
applies the fields it is given and returns the new user. Email needs
issue-send-confirm semantics, a throttle, and a failure mode that is not "the
field did not change", none of which a partial update expresses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.core.redis import get_redis
from app.email.sender import EmailSender, get_email_sender
from app.email.service import (
    delete_email,
    request_email,
    resend_verification,
    verify_email,
)

router = APIRouter(prefix="/v1", tags=["email"])

RedisDep = Depends(get_redis)
# A dependency, not a direct call, so tests override it with a recording double
# and the off-switch stays the only thing standing between a run and the network.
EmailSenderDep = Depends(get_email_sender)

_STRICT = ConfigDict(extra="forbid")


class SetEmailRequest(BaseModel):
    model_config = _STRICT

    # Validated by app/email/address.py, not by pydantic's EmailStr: the rules
    # we need (no control characters at all, explicit length caps, no quoted
    # local parts) are stricter and are enforced in one place that the sender
    # also re-checks.
    email: str


class VerifyEmailRequest(BaseModel):
    model_config = _STRICT

    token: str


@router.post("/me/email")
async def set_email(
    payload: SetEmailRequest,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
    sender: EmailSender = EmailSenderDep,
) -> dict[str, object]:
    return await request_email(
        session,
        redis,
        user_id=current_user.id,
        raw_email=payload.email,
        sender=sender,
    )


@router.post("/me/email/verify")
async def post_verify_email(
    payload: VerifyEmailRequest,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> dict[str, object]:
    return await verify_email(session, user_id=current_user.id, raw_token=payload.token)


@router.post("/me/email/resend")
async def post_resend_verification(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
    sender: EmailSender = EmailSenderDep,
) -> dict[str, object]:
    return await resend_verification(
        session,
        redis,
        user_id=current_user.id,
        sender=sender,
    )


@router.delete("/me/email")
async def remove_email(
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> dict[str, object]:
    return await delete_email(session, user_id=current_user.id)
