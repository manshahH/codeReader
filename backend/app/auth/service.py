from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import generate_refresh_token, refresh_token_hash
from app.config import Settings
from app.core.errors import ApiError
from app.core.events import alert_refresh_reuse
from app.core.security import encrypt_token
from app.models import AuthIdentity, BetaInvite, RefreshToken, User

REFRESH_COOKIE_NAME = "rt"
REFRESH_COOKIE_PATH = "/v1/auth"


@dataclass(frozen=True)
class GithubProfile:
    provider_user_id: str
    login: str
    display_name: str | None
    avatar_url: str | None


@dataclass(frozen=True)
class RefreshIssue:
    raw_token: str
    row: RefreshToken


def user_response(user: User, *, email_prefs: dict[str, bool]) -> dict[str, object]:
    """The client-visible user allowlist.

    `email_prefs` is a REQUIRED keyword argument rather than something this
    function fetches, for two reasons. This module is sync and the preference
    read needs the session; and making it required means a new call site cannot
    silently omit it and ship a user object the Profile screen renders as
    "reminders off" for everyone. There are only three call sites, so the cost
    of threading it is one line each.
    """
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "level": user.level,
        "timezone": user.timezone,
        "onboarded": user.onboarded,
        # A2 email capture (D-120(6)). `email` is the VERIFIED address or null;
        # `email_verified` is carried explicitly rather than left for the client
        # to infer from nullness, so the contract survives any future path that
        # could put an unverified address in `email`. `pending_email` is here
        # because the pending screen cannot name the mailbox to check without
        # it. email_verified_at (ops data) and the token table are NOT exposed.
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "pending_email": user.pending_email,
        # A3 (D-137). `reminder_local_time` was ALREADY promised by docs/05
        # section 3 ("Same user object as above plus reminder_local_time") and
        # was already accepted by PATCH /me, but it was never actually in this
        # allowlist -- so the client could set it and could never read it back.
        # Serialized as "HH:MM", matching the format PATCH /me validates.
        "reminder_local_time": (
            user.reminder_local_time.strftime("%H:%M")
            if user.reminder_local_time is not None
            else None
        ),
        # Consent, kept SEPARATE from the schedule above: a user can have
        # reminders consented with no time set, and the Profile screen has to
        # render that differently from "turned off" (D-137(6)).
        "email_prefs": email_prefs,
    }


async def _apply_beta_invite(session: AsyncSession, user: User, github_login: str) -> None:
    """Flip beta_allowed on if this handle is on the invite list (M8) --
    covers both "invited before ever logging in" (the row already exists at
    login time) and "invited after a first, then-rejected, login attempt"
    (they log in again and this re-checks). Never flips it off: revocation
    is an explicit admin action (revoke_beta_access), not an absence check.
    """
    if user.beta_allowed:
        return
    invited = await session.scalar(
        select(BetaInvite).where(BetaInvite.github_login == github_login),
    )
    if invited is not None:
        user.beta_allowed = True


async def upsert_github_user(
    session: AsyncSession,
    *,
    profile: GithubProfile,
    access_token: str,
    scopes: str | None,
    settings: Settings,
) -> User:
    identity = await session.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == "github",
            AuthIdentity.provider_user_id == profile.provider_user_id,
        ),
    )
    sealed_token = encrypt_token(access_token, settings.TOKEN_ENC_KEY)

    if identity is not None:
        user = await session.get(User, identity.user_id)
        if user is None:
            raise ApiError(500, "internal", "Identity is missing its user.")
        user.username = profile.login
        user.display_name = profile.display_name
        user.avatar_url = profile.avatar_url
        identity.provider_login = profile.login
        identity.access_token_enc = sealed_token
        identity.token_scopes = scopes
    else:
        username = profile.login
        existing_user = await session.scalar(select(User).where(User.username == username))
        if existing_user is not None:
            username = f"{profile.login}-{profile.provider_user_id}"

        user = User(
            username=username,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
        )
        session.add(user)
        await session.flush()

        identity = AuthIdentity(
            user_id=user.id,
            provider="github",
            provider_user_id=profile.provider_user_id,
            provider_login=profile.login,
            access_token_enc=sealed_token,
            token_scopes=scopes,
        )
        session.add(identity)

    await _apply_beta_invite(session, user, profile.login)
    await session.flush()
    return user


async def invite_to_beta(session: AsyncSession, github_login: str) -> dict[str, bool | str]:
    """Admin path (CLAUDE.md M8): invite a GitHub handle. Idempotent -- an
    already-invited handle is a no-op, not an error. If a user with this
    username already exists (logged in before being invited), flips their
    access on immediately instead of waiting for their next login.
    """
    existing_invite = await session.scalar(
        select(BetaInvite).where(BetaInvite.github_login == github_login),
    )
    if existing_invite is None:
        session.add(BetaInvite(github_login=github_login))

    user = await session.scalar(select(User).where(User.username == github_login))
    user_flipped = False
    if user is not None and not user.beta_allowed:
        user.beta_allowed = True
        user_flipped = True

    await session.flush()
    await session.commit()
    return {
        "github_login": github_login,
        "already_invited": existing_invite is not None,
        "user_flipped": user_flipped,
    }


async def revoke_beta_access(session: AsyncSession, github_login: str) -> dict[str, bool | str]:
    """Admin path: remove a handle from the invite list AND revoke an
    existing user's access, so a mid-beta removal takes effect (the next
    refresh call 401s, per rotate_refresh_token's beta_allowed check) rather
    than only blocking a login that already happened.
    """
    await session.execute(delete(BetaInvite).where(BetaInvite.github_login == github_login))

    user = await session.scalar(select(User).where(User.username == github_login))
    user_revoked = False
    if user is not None and user.beta_allowed:
        user.beta_allowed = False
        user_revoked = True

    await session.flush()
    await session.commit()
    return {"github_login": github_login, "user_revoked": user_revoked}


async def issue_refresh_token(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    settings: Settings,
    family_id: uuid.UUID | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> RefreshIssue:
    raw_token = generate_refresh_token()
    now = dt.datetime.now(dt.UTC)
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        token_hash=refresh_token_hash(raw_token),
        issued_at=now,
        expires_at=now + dt.timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        user_agent=user_agent,
        ip=ip,
    )
    session.add(row)
    await session.flush()
    return RefreshIssue(raw_token=raw_token, row=row)


async def rotate_refresh_token(
    session: AsyncSession,
    *,
    raw_token: str | None,
    settings: Settings,
    request_id: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[User, RefreshIssue]:
    if not raw_token:
        raise ApiError(401, "invalid_token", "Refresh token is required.")

    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == refresh_token_hash(raw_token)),
    )
    if row is None:
        raise ApiError(401, "invalid_token", "Refresh token is invalid.")

    now = dt.datetime.now(dt.UTC)
    if row.rotated_at is not None or row.revoked_at is not None:
        alert_refresh_reuse(
            token_id=row.id,
            family_id=row.family_id,
            user_id=row.user_id,
            request_id=request_id,
        )
        # TODO(M2/D-4): kill the refresh token family here after MVP alert-only mode.
        raise ApiError(401, "invalid_token", "Refresh token is invalid.")
    if row.expires_at <= now:
        raise ApiError(401, "invalid_token", "Refresh token is invalid.")

    user = await session.get(User, row.user_id)
    if user is None:
        raise ApiError(401, "invalid_token", "Refresh token is invalid.")
    if settings.BETA_GATE_ENABLED and not user.beta_allowed:
        # Beta access revoked since this token was issued (M8): treat exactly
        # like an invalid token rather than a distinct error, so a revoked
        # user is silently logged out on their next refresh (within
        # ACCESS_TOKEN_TTL of the revocation) instead of leaking whether the
        # username is a known account. Gated on BETA_GATE_ENABLED (D-92) so
        # a gate-off login can't be issued a session in github_callback and
        # then immediately 401 here -- both enforcement points must agree.
        raise ApiError(401, "invalid_token", "Refresh token is invalid.")

    row.rotated_at = now
    issue = await issue_refresh_token(
        session,
        user_id=user.id,
        settings=settings,
        family_id=row.family_id,
        user_agent=user_agent,
        ip=ip,
    )
    await session.flush()
    return user, issue


async def revoke_refresh_family(session: AsyncSession, *, raw_token: str | None) -> None:
    if not raw_token:
        return
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == refresh_token_hash(raw_token)),
    )
    if row is None:
        return
    now = dt.datetime.now(dt.UTC)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now),
    )
    await session.flush()