"""Email capture and verification (A2, D-120).

State machine, in one place so it can be read in one sitting:

    no email        -> POST /me/email      -> pending
    pending         -> POST /me/email/verify (good token) -> verified
    pending         -> POST /me/email/resend -> pending (new token, old dead)
    verified        -> POST /me/email      -> verified + pending (BOTH live)
    verified+pending-> verify              -> verified (new address promoted)
    anything        -> DELETE /me/email    -> no email

The load-bearing rule is that `users.email` only ever holds a VERIFIED address.
A new address waits in `pending_email` and the old one keeps receiving until the
new one is confirmed, so a typo cannot silently kill the notification channel
and A3 never has to ask whether an address is deliverable.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import logging
import secrets
import uuid

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.core.ratelimit import check_token_bucket
from app.email.address import InvalidEmailError, mask_email, normalize_email
from app.email.messages import build_verification_email
from app.email.sender import EmailSender, EmailSendError
from app.models import EmailVerificationToken, User

logger = logging.getLogger(__name__)

TOKEN_BYTES = 32

# D-120(5): every verification failure is this one response. Unknown, expired,
# consumed, invalidated, another user's token, and losing the uniqueness race
# are indistinguishable from outside. Anything finer is an oracle -- "already
# used" confirms the token was real, "belongs to another user" confirms an
# address is registered.
_VERIFY_FAILURE_CODE = "verification_failed"
_VERIFY_FAILURE_MESSAGE = "That verification link is not valid or has expired."


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def generate_verification_token() -> str:
    """Same generator as refresh tokens (auth/tokens.py): 256 bits of CSPRNG."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def verification_token_hash(token: str) -> bytes:
    """Same storage as refresh_tokens.token_hash (auth/tokens.py).

    Unsalted single-round sha256 is correct for a high-entropy random token:
    there is no dictionary to precompute, so a KDF would cost latency and buy
    nothing.
    """
    return hashlib.sha256(token.encode("utf-8")).digest()


def _address_bucket_key(email: str) -> str:
    """Rate-limit key for an address, keyed by DIGEST rather than the address.

    Redis is not where our PII inventory should quietly grow a second copy, and
    a digest is a perfectly good bucket identity.
    """
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:32]


async def _enforce_send_throttle(redis: Redis, *, user_id: uuid.UUID, email: str) -> None:
    """Throttle per USER and per TARGET ADDRESS. Both, not either.

    Per-user alone lets one account walk an address list, sending a mail to each.
    Per-address alone lets many accounts converge on one mailbox. Only the pair
    closes both, so both are enforced and either one denying is a denial.

    Two layers, and they are scoped DIFFERENTLY on purpose:

    * The short cooldown is keyed on the TARGET ADDRESS only, not on the user.
      It is a mailbox-protection floor: no address receives two verification
      mails inside the window, whoever asks. Keying it per-user as well was the
      first shape and it was wrong -- it blocked the single most likely thing a
      user does after a typo, which is immediately retype the address. Making
      someone wait 60 seconds to correct a typo is a worse product for no
      security gain, because the hourly cap below is what actually bounds a user
      walking an address list.
    * The hourly cap IS enforced per user and per address. Per-user alone lets
      one account walk an address list; per-address alone lets many accounts
      converge on one mailbox. Only the pair closes both.
    """
    settings = get_settings()
    addr_key = _address_bucket_key(email)

    cooldown_key = f"emailsend:cooldown:addr:{addr_key}"
    # SET NX EX: the first caller claims the window, everyone else inside it is
    # refused. Atomic, so two concurrent requests cannot both claim it.
    claimed = await redis.set(
        cooldown_key,
        "1",
        ex=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_S,
        nx=True,
    )
    if not claimed:
        ttl = await redis.ttl(cooldown_key)
        retry_after = (
            max(1, int(ttl)) if ttl and ttl > 0 else settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_S
        )
        raise ApiError(
            429,
            "rate_limited",
            "Wait a moment before requesting another verification email.",
            headers={"Retry-After": str(retry_after)},
        )

    for scope, identity in (("user", str(user_id)), ("addr", addr_key)):
        result = await check_token_bucket(
            redis,
            key=f"rl:emailsend:{scope}:{identity}",
            limit=settings.EMAIL_VERIFICATION_SENDS_PER_HOUR,
            window_seconds=3600,
        )
        if not result.allowed:
            raise ApiError(
                429,
                "rate_limited",
                "Too many verification emails requested. Try again later.",
                headers=result.headers,
            )


async def _invalidate_outstanding(
    session: AsyncSession, user_id: uuid.UUID, *, now: dt.datetime
) -> None:
    """Issuing a new token kills the user's outstanding ones (D-120(4)).

    Stamped rather than deleted so "why did my link stop working" stays
    answerable in one query.
    """
    await session.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.consumed_at.is_(None),
            EmailVerificationToken.invalidated_at.is_(None),
        )
        .values(invalidated_at=now),
    )


async def _issue_and_send(
    session: AsyncSession,
    sender: EmailSender,
    *,
    user: User,
    email: str,
) -> None:
    now = _now()
    settings = get_settings()

    await _invalidate_outstanding(session, user.id, now=now)

    raw_token = generate_verification_token()
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            email=email,
            token_hash=verification_token_hash(raw_token),
            expires_at=now + dt.timedelta(hours=settings.EMAIL_VERIFICATION_TTL_H),
        ),
    )
    user.pending_email = email
    await session.flush()

    message = build_verification_email(
        to=email,
        token=raw_token,
        ttl_hours=settings.EMAIL_VERIFICATION_TTL_H,
    )
    try:
        await sender.send(message)
    except EmailSendError as exc:
        raise ApiError(
            503,
            "email_send_failed",
            "Could not send the verification email. Try again shortly.",
        ) from exc

    # The FACT of the send, never the token and never the full address.
    logger.info(
        "email.verification.issued",
        extra={"user_id": str(user.id), "to": mask_email(email)},
    )


async def _load_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise ApiError(401, "invalid_token", "Access token is invalid.")
    return user


async def request_email(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: uuid.UUID,
    raw_email: str,
    sender: EmailSender,
) -> dict[str, object]:
    """Set or replace pending_email and send a verification link.

    Returns the SAME payload whether or not the address is already verified on
    another account (D-120(5)). We do not check, on purpose: checking would only
    let us behave differently, and behaving differently is the leak. The
    uniqueness index settles the conflict at verify time instead.
    """
    try:
        email = normalize_email(raw_email)
    except InvalidEmailError as exc:
        raise ApiError(400, "validation_error", str(exc)) from exc

    user = await _load_user(session, user_id)

    if user.email is not None and user.email.lower() == email:
        # Re-submitting the address already verified on this account. Nothing to
        # prove, and sending a link would be a self-inflicted mail we would then
        # have to explain in the UI.
        raise ApiError(
            409,
            "email_already_verified",
            "That address is already confirmed on your account.",
        )

    await _enforce_send_throttle(redis, user_id=user.id, email=email)
    await _issue_and_send(session, sender, user=user, email=email)
    await session.commit()
    return email_state(user)


async def resend_verification(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: uuid.UUID,
    sender: EmailSender,
) -> dict[str, object]:
    """Reissue for the address already pending. Subject to the same throttle."""
    user = await _load_user(session, user_id)
    if user.pending_email is None:
        raise ApiError(
            409,
            "no_pending_email",
            "There is no address waiting to be confirmed.",
        )

    email = user.pending_email
    await _enforce_send_throttle(redis, user_id=user.id, email=email)
    await _issue_and_send(session, sender, user=user, email=email)
    await session.commit()
    return email_state(user)


async def verify_email(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    raw_token: str,
) -> dict[str, object]:
    """Consume a token and promote the address it was issued for.

    Promotes `token.email`, NOT `user.pending_email`. They are usually the same,
    but if the user submitted a second address after this token was issued, the
    stale link must not promote the newer one. Storing the target on the token
    is what makes that impossible rather than merely unlikely.
    """
    failure = ApiError(400, _VERIFY_FAILURE_CODE, _VERIFY_FAILURE_MESSAGE)

    if not raw_token or not isinstance(raw_token, str):
        raise failure

    digest = verification_token_hash(raw_token)
    row = await session.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == digest),
    )
    if row is None:
        raise failure

    # The lookup above narrowed the row; THIS is the comparison the code
    # branches on, and it is constant-time. (Refresh tokens match on DB equality
    # alone -- see D-120(4); this is a deliberate strengthening here, not a
    # change to that path.)
    if not hmac.compare_digest(bytes(row.token_hash), digest):
        raise failure

    now = _now()
    if row.consumed_at is not None or row.invalidated_at is not None:
        raise failure
    if row.expires_at <= now:
        raise failure
    # Another user's token. Same failure as every other case: saying "not yours"
    # would confirm the token is real and that the address is registered.
    if row.user_id != user_id:
        raise failure

    user = await _load_user(session, user_id)

    # Read the target address into a local BEFORE any flush that can fail. On a
    # uniqueness rollback every ORM attribute on `row` is expired, and touching
    # one then would trigger a lazy refresh outside the async context (a
    # MissingGreenlet, i.e. a 500 instead of the generic 400 this path owes).
    target_email = row.email

    row.consumed_at = now
    await _invalidate_outstanding(session, user.id, now=now)

    user.email = target_email
    user.email_verified_at = now
    user.pending_email = None

    try:
        # Savepoint: the partial unique index can reject this if another account
        # verified the same address first (D-120(3)). Without the nested block
        # the IntegrityError would poison the outer transaction and we could not
        # answer at all.
        async with session.begin_nested():
            await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        logger.info(
            "email.verification.conflict",
            extra={"user_id": str(user_id), "to": mask_email(target_email)},
        )
        raise failure from exc

    await session.commit()
    logger.info(
        "email.verification.confirmed",
        extra={"user_id": str(user.id), "to": mask_email(target_email)},
    )
    return email_state(user)


async def delete_email(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[str, object]:
    """Withdraw the address entirely.

    Consent that cannot be withdrawn in-product is not consent, so this is a
    first-class route rather than a support ticket. Clears all three fields and
    invalidates outstanding tokens in one transaction, so there is no window in
    which a stale link could re-add an address the user just removed.
    """
    user = await _load_user(session, user_id)
    now = _now()

    await _invalidate_outstanding(session, user.id, now=now)
    user.email = None
    user.email_verified_at = None
    user.pending_email = None

    await session.commit()
    logger.info("email.deleted", extra={"user_id": str(user.id)})
    return email_state(user)


def email_state(user: User) -> dict[str, object]:
    """The owner-visible email state (D-120(6)).

    `pending_email` is here because the pending screen is unrenderable without
    it: "we sent a link to ___, resend?" needs the address, and a bare boolean
    produces a screen that cannot tell the user which mailbox to check -- which
    is exactly the typo case this whole design exists to make visible. It is not
    a new leak vector: /me is self-scoped by bearer token and the value is a
    string this same user typed minutes ago.
    """
    return {
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "pending_email": user.pending_email,
    }
