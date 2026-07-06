from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import generate_refresh_token, refresh_token_hash
from app.config import Settings
from app.core.errors import ApiError
from app.core.events import alert_refresh_reuse
from app.core.security import encrypt_token
from app.models import AuthIdentity, RefreshToken, User

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


def user_response(user: User) -> dict[str, str | bool | None]:
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "level": user.level,
        "timezone": user.timezone,
        "onboarded": True,
    }


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
        await session.flush()
        return user

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
    await session.flush()
    return user


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