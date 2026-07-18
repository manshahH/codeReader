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
from app.schemas.admin import BetaInviteRequest, OutageFreezeRequest
from app.streak.service import grant_initial_freezes, outage_freeze

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


@router.post("/admin/streak/outage-freeze")
async def admin_streak_outage_freeze(
    payload: OutageFreezeRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> dict:
    """The "big red button" (docs/10 A1): a service outage must never cost a
    streak. Writes a freeze_used row for the given local date without spending
    any user's balance and without mutating any current_streak -- see D-116.
    """
    _require_admin_token(x_admin_token)
    return await outage_freeze(session, payload.local_date)


@router.post("/admin/streak/grant-initial-freezes")
async def admin_streak_grant_initial_freezes(
    payload: OutageFreezeRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> dict:
    """One-time A1 backfill (D-118): give pre-A1 accounts the starting freeze
    balance their user_stats row was created too early to receive. Idempotent,
    capped, and ledger-explained. `local_date` stamps the adjusted rows.
    """
    _require_admin_token(x_admin_token)
    return await grant_initial_freezes(session, payload.local_date)


@router.get("/admin/reviews")
async def admin_reviews(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: AsyncSession = DbSessionDep,
) -> list[dict]:
    _require_admin_token(x_admin_token)
    return await list_reviews(session)
