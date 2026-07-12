"""GET /admin/metrics: minimal ops dashboard (M7 observability).

Deliberately mounted OUTSIDE /v1 -- docs/05 section 7 reserves /admin/* for
a separate internal app behind its own auth, out of the public API
contract. Building that separate app/auth system is out of M7's scope; this
is a pragmatic placeholder gated by a shared-secret header instead (see
docs/07-decisions.md for the divergence entry), swappable for a real admin
app later without moving the public contract at all.
"""

from __future__ import annotations

import datetime as dt
import hmac

from fastapi import APIRouter, Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import collect_metrics, compute_retention, list_reviews
from app.auth.deps import DbSessionDep
from app.auth.service import invite_to_beta, revoke_beta_access
from app.config import get_settings
from app.core.errors import ApiError
from app.core.redis import get_redis
from app.schemas.admin import BetaInviteRequest

router = APIRouter(tags=["admin"])
RedisDep = Depends(get_redis)


def _require_admin_token(x_admin_token: str | None) -> None:
    configured = get_settings().ADMIN_METRICS_TOKEN
    if not configured:
        # No token configured: treat the endpoint as disabled rather than
        # silently open. 404, not 403 -- don't confirm the route exists.
        raise ApiError(404, "not_found", "Not found.")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, configured):
        raise ApiError(403, "forbidden", "Invalid admin token.")


@router.get("/admin/metrics")
async def admin_metrics(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
    redis: Redis = RedisDep,
) -> dict:
    _require_admin_token(x_admin_token)
    job_scheduler = getattr(request.app.state, "job_scheduler", None)
    return await collect_metrics(session, redis, job_scheduler)


@router.get("/admin/retention")
async def admin_retention(
    cohort_start: dt.date,
    offset_days: int = 1,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> dict:
    _require_admin_token(x_admin_token)
    return await compute_retention(session, cohort_start, offset_days)


@router.post("/admin/beta/invite")
async def admin_beta_invite(
    payload: BetaInviteRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> dict:
    _require_admin_token(x_admin_token)
    return await invite_to_beta(session, payload.github_login)


@router.post("/admin/beta/revoke")
async def admin_beta_revoke(
    payload: BetaInviteRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> dict:
    _require_admin_token(x_admin_token)
    return await revoke_beta_access(session, payload.github_login)


@router.get("/admin/reviews")
async def admin_reviews(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> list[dict]:
    _require_admin_token(x_admin_token)
    return await list_reviews(session)
