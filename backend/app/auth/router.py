from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import DbSessionDep
from app.auth.oauth import (
    GithubClient,
    authorize_url,
    create_pkce_pair,
    create_state,
    get_github_client,
)
from app.auth.service import (
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    GithubProfile,
    issue_refresh_token,
    revoke_refresh_family,
    rotate_refresh_token,
    upsert_github_user,
    user_response,
)
from app.auth.tokens import issue_access_token
from app.config import get_settings
from app.core.errors import ApiError, request_id
from app.core.network import resolve_client_ip
from app.core.ratelimit import check_token_bucket
from app.core.redis import get_redis
from app.email.deliveries import email_preferences

router = APIRouter(prefix="/v1/auth", tags=["auth"])
OAUTH_STATE_TTL_SECONDS = 600
RedisDep = Depends(get_redis)
GithubClientDep = Depends(get_github_client)


def _client_ip(request: Request) -> str:
    return resolve_client_ip(request, get_settings().TRUSTED_PROXY_COUNT)


def _login_redirect(error: str) -> str:
    origin = get_settings().APP_ORIGIN.rstrip("/")
    return f"{origin}/login?error={error}"


def _refresh_cookie_kwargs() -> dict[str, object]:
    settings = get_settings()
    return {
        "key": REFRESH_COOKIE_NAME,
        "httponly": True,
        "secure": True,
        "samesite": "lax",
        "path": REFRESH_COOKIE_PATH,
        "max_age": settings.REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60,
    }


async def _enforce_auth_rate_limit(request: Request, redis: Redis) -> dict[str, str]:
    settings = get_settings()
    result = await check_token_bucket(
        redis,
        key=f"rl:auth:{_client_ip(request)}",
        limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
    )
    if not result.allowed:
        raise ApiError(429, "rate_limited", "Too many requests.", headers=result.headers)
    return result.headers


@router.get("/github/start")
async def github_start(
    request: Request,
    redis: Redis = RedisDep,
) -> RedirectResponse:
    headers = await _enforce_auth_rate_limit(request, redis)
    settings = get_settings()
    state = create_state()
    pkce = create_pkce_pair()
    await redis.set(
        f"oauth:github:state:{state}",
        json.dumps({"code_verifier": pkce.verifier}),
        ex=OAUTH_STATE_TTL_SECONDS,
        nx=True,
    )
    return RedirectResponse(
        authorize_url(state=state, code_challenge=pkce.challenge, settings=settings),
        status_code=302,
        headers=headers,
    )


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    redis: Redis = RedisDep,
    session: AsyncSession = DbSessionDep,
    github: GithubClient = GithubClientDep,
) -> RedirectResponse:
    headers = await _enforce_auth_rate_limit(request, redis)
    if error:
        return RedirectResponse(_login_redirect("oauth_denied"), status_code=302, headers=headers)
    if not code or not state:
        return RedirectResponse(_login_redirect("oauth_state"), status_code=302, headers=headers)

    state_payload = await redis.getdel(f"oauth:github:state:{state}")
    if state_payload is None:
        return RedirectResponse(_login_redirect("oauth_state"), status_code=302, headers=headers)

    try:
        code_verifier = json.loads(state_payload)["code_verifier"]
        token = await github.exchange_code(code=code, code_verifier=code_verifier)
        github_profile = await github.fetch_profile(access_token=token.access_token)
        user = await upsert_github_user(
            session,
            profile=GithubProfile(
                provider_user_id=github_profile.id,
                login=github_profile.login,
                display_name=github_profile.name,
                avatar_url=github_profile.avatar_url,
            ),
            access_token=token.access_token,
            scopes=token.scope,
            settings=get_settings(),
        )
        if get_settings().BETA_GATE_ENABLED and not user.beta_allowed:
            # M8: the app is not open to the world -- the user row is kept
            # (so an admin can invite them by username later without a fresh
            # login), but no session is issued. Commit here, not rollback:
            # the upsert itself (username/avatar refresh, or the brand-new
            # row) is real state worth keeping regardless of beta status.
            await session.commit()
            return RedirectResponse(
                _login_redirect("beta_required"),
                status_code=302,
                headers=headers,
            )
        refresh_issue = await issue_refresh_token(
            session,
            user_id=user.id,
            settings=get_settings(),
            user_agent=request.headers.get("user-agent"),
            ip=_client_ip(request),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    response = RedirectResponse(get_settings().APP_ORIGIN, status_code=302, headers=headers)
    response.set_cookie(value=refresh_issue.raw_token, **_refresh_cookie_kwargs())
    return response


@router.post("/refresh")
async def refresh(
    request: Request,
    redis: Redis = RedisDep,
    session: AsyncSession = DbSessionDep,
) -> JSONResponse:
    headers = await _enforce_auth_rate_limit(request, redis)
    try:
        user, refresh_issue = await rotate_refresh_token(
            session,
            raw_token=request.cookies.get(REFRESH_COOKIE_NAME),
            settings=get_settings(),
            request_id=request_id(request),
            user_agent=request.headers.get("user-agent"),
            ip=_client_ip(request),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    access_token = issue_access_token(
        user_id=user.id,
        secret=get_settings().jwt_secrets[0],
        ttl_seconds=get_settings().ACCESS_TOKEN_TTL,
    )
    response = JSONResponse(
        content={
            "access_token": access_token,
            "expires_in": get_settings().ACCESS_TOKEN_TTL,
            "user": user_response(user, email_prefs=await email_preferences(session, user.id)),
        },
        headers=headers,
    )
    response.set_cookie(value=refresh_issue.raw_token, **_refresh_cookie_kwargs())
    return response


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    redis: Redis = RedisDep,
    session: AsyncSession = DbSessionDep,
) -> Response:
    headers = await _enforce_auth_rate_limit(request, redis)
    try:
        await revoke_refresh_family(session, raw_token=request.cookies.get(REFRESH_COOKIE_NAME))
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    response = Response(status_code=204, headers=headers)
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response