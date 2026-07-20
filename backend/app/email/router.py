"""Email capture routes (A2, D-120; docs/05 section 3).

Deliberately NOT folded into PATCH /me. PATCH /me is a partial update: it
applies the fields it is given and returns the new user. Email needs
issue-send-confirm semantics, a throttle, and a failure mode that is not "the
field did not change", none of which a partial update expresses.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, CurrentUserDep, DbSessionDep
from app.core.errors import ApiError
from app.core.redis import get_redis
from app.email.deliveries import email_preferences, suppress, unsuppress
from app.email.sender import EmailSender, get_email_sender
from app.email.service import (
    delete_email,
    request_email,
    resend_verification,
    verify_email,
)
from app.email.unsubscribe import InvalidUnsubscribeToken, parse_unsubscribe_token

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


# ---------------------------------------------------------------------------
# A3 notification preferences and unsubscribe (D-137(6), (7))
# ---------------------------------------------------------------------------


class EmailPrefsRequest(BaseModel):
    model_config = _STRICT

    reminders_enabled: bool | None = None
    recap_enabled: bool | None = None


@router.patch("/me/email-prefs")
async def patch_email_prefs(
    payload: EmailPrefsRequest,
    current_user: CurrentUser = CurrentUserDep,
    session: AsyncSession = DbSessionDep,
) -> dict[str, bool]:
    """The in-app half of the same switch the email footer flips.

    Reads and writes the SAME `email_suppressions` rows the one-click link
    does, so the Profile toggle and the unsubscribe link can never disagree.
    Turning a type back on is the only path that deletes a suppression, and it
    is authenticated, which is the point: re-consent has to be a deliberate act
    by the account owner (D-137(6)).
    """
    updates = payload.model_dump(exclude_unset=True)
    for field, kind in (("reminders_enabled", "reminder"), ("recap_enabled", "recap")):
        if field not in updates or updates[field] is None:
            continue
        if updates[field]:
            await unsuppress(session, current_user.id, kind)
        else:
            await suppress(
                session,
                current_user.id,
                kind,
                reason="unsubscribe",
                source="profile",
            )
    await session.commit()
    return await email_preferences(session, current_user.id)


async def _apply_unsubscribe(session: AsyncSession, token: str) -> dict[str, str]:
    try:
        user_id, kind = parse_unsubscribe_token(token)
    except InvalidUnsubscribeToken as exc:
        # ONE generic failure, same discipline as D-120(5). A response that
        # distinguished "bad signature" from "unknown user" would confirm which
        # user ids exist to anyone holding a token they cannot verify.
        raise ApiError(
            400,
            "unsubscribe_failed",
            "That unsubscribe link is not valid.",
        ) from exc

    await suppress(session, user_id, kind, reason="unsubscribe", source="email_link")
    await session.commit()
    return {"unsubscribed": kind}


@router.post("/unsubscribe")
async def post_unsubscribe(
    token: Annotated[str, Query()],
    session: AsyncSession = DbSessionDep,
) -> dict[str, str]:
    """RFC 8058 one-click. UNAUTHENTICATED, and that is the requirement.

    A mail provider POSTs this with no session and no cookies, and a user
    clicking from their inbox may not be signed in. An unsubscribe that
    bounces to OAuth is a broken unsubscribe, and a broken unsubscribe is how
    you get reported as spam instead.

    The token comes from the QUERY STRING and the BODY IS IGNORED, because the
    body a provider sends is the fixed form field `List-Unsubscribe=One-Click`
    rather than anything of ours. No CSRF token either: there is no session to
    ride, and the worst an attacker achieves is stopping mail the owner turns
    back on in one click.

    IDEMPOTENT. Providers may deliver the POST more than once and users click
    the link in more than one email; a second call is a 200, not an error.
    """
    return await _apply_unsubscribe(session, token)


@router.get("/unsubscribe/preview")
async def get_unsubscribe_preview(token: Annotated[str, Query()]) -> dict[str, str]:
    """What this token would turn off, WITHOUT turning it off.

    The SPA page calls this to render "turn off reminders?" before the user
    presses anything. It is a separate read-only route rather than a GET on
    /unsubscribe precisely because a GET must never act: prefetchers, corporate
    link scanners and mail-client previews all follow GETs, and any of them
    would silently unsubscribe the user (D-137(7)).

    Returns the kind only. It deliberately does not return the address or the
    user id: the token proves possession of a link, not of the account.
    """
    try:
        _, kind = parse_unsubscribe_token(token)
    except InvalidUnsubscribeToken as exc:
        raise ApiError(
            400,
            "unsubscribe_failed",
            "That unsubscribe link is not valid.",
        ) from exc
    return {"kind": kind}
