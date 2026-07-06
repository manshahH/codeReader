from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import TokenError, TokenExpiredError, verify_access_token
from app.config import get_settings
from app.core.errors import ApiError
from app.db import create_engine, create_session_factory


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        engine = create_engine()
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.rollback()
        await engine.dispose()
        return

    async with session_factory() as session:
        yield session


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    plan: str
    jti: str


async def require_access_token(request: Request) -> CurrentUser:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "invalid_token", "Access token is required.")

    try:
        claims = verify_access_token(token, get_settings().jwt_secrets)
    except TokenExpiredError as exc:
        raise ApiError(401, exc.code, exc.message) from exc
    except TokenError as exc:
        raise ApiError(401, exc.code, exc.message) from exc

    return CurrentUser(id=claims.sub, plan=claims.plan, jti=claims.jti)


CurrentUserDep = Depends(require_access_token)
DbSessionDep = Depends(get_db_session)