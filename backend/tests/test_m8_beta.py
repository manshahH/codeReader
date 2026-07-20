"""M8 beta readiness: allowlisted login, admin invite/revoke, D1/D7
retention, job-runner health, and empty-session rate on /admin/metrics.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.oauth import GithubToken, GithubUserProfile, get_github_client
from app.auth.service import (
    REFRESH_COOKIE_NAME,
    GithubProfile,
    invite_to_beta,
    issue_refresh_token,
    revoke_beta_access,
    rotate_refresh_token,
    upsert_github_user,
)
from app.config import Settings, get_settings
from app.core.errors import ApiError
from app.jobs.runner import JobScheduler
from app.main import create_app
from app.models import BetaInvite, DailySession, User
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401 (autouse fixture, must be imported to activate)
    clean_redis,  # noqa: F401 (autouse fixture, must be imported to activate)
    m4_env,  # noqa: F401 (autouse fixture, must be imported to activate)
    make_user,
)


@pytest.fixture(autouse=True)
def admin_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_METRICS_TOKEN", "test-admin-metrics-token")
    get_settings.cache_clear()


def _settings() -> Settings:
    return get_settings()


class FakeGithubClient:
    def __init__(self, login: str) -> None:
        self.login = login

    async def exchange_code(self, *, code: str, code_verifier: str) -> GithubToken:  # noqa: ARG002
        return GithubToken(access_token="gho_fake", scope="read:user")

    async def fetch_profile(self, *, access_token: str) -> GithubUserProfile:  # noqa: ARG002
        return GithubUserProfile(id="99999", login=self.login, name=None, avatar_url=None)


async def _oauth_callback(client: AsyncClient):
    start = await client.get("/v1/auth/github/start", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    return await client.get(
        f"/v1/auth/github/callback?code=x&state={state}",
        follow_redirects=False,
    )


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


# --- auth/service.py: invite_to_beta / revoke_beta_access --------------------


@pytest.mark.asyncio
async def test_invite_to_beta_is_idempotent(db_session: AsyncSession) -> None:
    first = await invite_to_beta(db_session, "somehandle")
    second = await invite_to_beta(db_session, "somehandle")

    assert first["already_invited"] is False
    assert second["already_invited"] is True
    invites = (
        await db_session.scalars(
            select(BetaInvite).where(BetaInvite.github_login == "somehandle"),
        )
    ).all()
    assert len(invites) == 1


@pytest.mark.asyncio
async def test_invite_to_beta_flips_an_already_existing_user_immediately(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session, username="latecomer")
    assert user.beta_allowed is False

    result = await invite_to_beta(db_session, "latecomer")

    assert result["user_flipped"] is True
    await db_session.refresh(user)
    assert user.beta_allowed is True


@pytest.mark.asyncio
async def test_revoke_beta_access_removes_invite_and_flips_user_off(
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session, username="soon-revoked")
    await invite_to_beta(db_session, "soon-revoked")
    await db_session.refresh(user)
    assert user.beta_allowed is True

    result = await revoke_beta_access(db_session, "soon-revoked")

    assert result["user_revoked"] is True
    await db_session.refresh(user)
    assert user.beta_allowed is False
    assert (
        await db_session.scalar(
            select(BetaInvite).where(BetaInvite.github_login == "soon-revoked"),
        )
    ) is None


@pytest.mark.asyncio
async def test_revoke_beta_access_on_never_invited_handle_is_a_safe_no_op(
    db_session: AsyncSession,
) -> None:
    result = await revoke_beta_access(db_session, "never-existed")

    assert result["user_revoked"] is False


# --- login/refresh gating -----------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_github_user_leaves_beta_allowed_false_when_not_invited(
    db_session: AsyncSession,
) -> None:
    user = await upsert_github_user(
        db_session,
        profile=GithubProfile(
            provider_user_id="1",
            login="uninvited-handle",
            display_name=None,
            avatar_url=None,
        ),
        access_token="tok",
        scopes="read:user",
        settings=_settings(),
    )

    assert user.beta_allowed is False


@pytest.mark.asyncio
async def test_upsert_github_user_flips_beta_allowed_when_invited_first(
    db_session: AsyncSession,
) -> None:
    await invite_to_beta(db_session, "invited-handle")

    user = await upsert_github_user(
        db_session,
        profile=GithubProfile(
            provider_user_id="2",
            login="invited-handle",
            display_name=None,
            avatar_url=None,
        ),
        access_token="tok",
        scopes="read:user",
        settings=_settings(),
    )

    assert user.beta_allowed is True


@pytest.mark.asyncio
async def test_login_denied_when_not_beta_allowed_no_session_issued(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BETA_GATE_ENABLED", "true")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: FakeGithubClient("outsider")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        callback = await _oauth_callback(client)

    assert callback.status_code == 302
    assert "error=beta_required" in callback.headers["location"]
    assert REFRESH_COOKIE_NAME not in callback.cookies

    # The user row IS kept, but not beta_allowed -- an admin can invite them
    # by username without a fresh login.
    user = await db_session.scalar(select(User).where(User.username == "outsider"))
    assert user is not None
    assert user.beta_allowed is False


@pytest.mark.asyncio
async def test_login_succeeds_when_invited(db_session: AsyncSession) -> None:
    await invite_to_beta(db_session, "welcomed")

    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: FakeGithubClient("welcomed")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        callback = await _oauth_callback(client)

    assert callback.status_code == 302
    assert "error=" not in callback.headers["location"]
    assert REFRESH_COOKIE_NAME in callback.cookies


# --- D-92: BETA_GATE_ENABLED switch --------------------------------------------


@pytest.mark.asyncio
async def test_login_succeeds_when_beta_gate_disabled_for_uninvited_user(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate off (D-92 default): an uninvited GitHub user still gets a real,
    usable session -- not just a cookie-setting callback, but one that
    actually survives a subsequent /auth/refresh (rotate_refresh_token has
    its own independent beta_allowed check that must also respect the flag).
    """
    monkeypatch.setenv("BETA_GATE_ENABLED", "false")
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: FakeGithubClient("gate-off-stranger")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        callback = await _oauth_callback(client)
        assert callback.status_code == 302
        assert "error=" not in callback.headers["location"]
        assert REFRESH_COOKIE_NAME in callback.cookies

        refresh = await client.post("/v1/auth/refresh")

    assert refresh.status_code == 200
    assert refresh.json()["user"]["username"] == "gate-off-stranger"

    user = await db_session.scalar(select(User).where(User.username == "gate-off-stranger"))
    assert user is not None
    assert user.beta_allowed is False  # allowlist state itself is untouched


@pytest.mark.asyncio
async def test_login_still_denied_when_beta_gate_enabled_for_uninvited_user(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate on: the exact same uninvited user is still refused -- flipping
    BETA_GATE_ENABLED=true must restore current behaviour with no other
    change.
    """
    monkeypatch.setenv("BETA_GATE_ENABLED", "true")
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_github_client] = lambda: FakeGithubClient("gate-on-stranger")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        callback = await _oauth_callback(client)

    assert callback.status_code == 302
    assert "error=beta_required" in callback.headers["location"]
    assert REFRESH_COOKIE_NAME not in callback.cookies

    user = await db_session.scalar(select(User).where(User.username == "gate-on-stranger"))
    assert user is not None
    assert user.beta_allowed is False


@pytest.mark.asyncio
async def test_refresh_401s_after_beta_access_is_revoked_mid_session(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BETA_GATE_ENABLED", "true")
    get_settings.cache_clear()
    user = await make_user(db_session, username="revoked-midway")
    await invite_to_beta(db_session, "revoked-midway")
    await db_session.refresh(user)

    issue = await issue_refresh_token(db_session, user_id=user.id, settings=_settings())
    await db_session.commit()

    await revoke_beta_access(db_session, "revoked-midway")

    with pytest.raises(ApiError) as exc_info:
        await rotate_refresh_token(
            db_session,
            raw_token=issue.raw_token,
            settings=_settings(),
            request_id="req_test",
        )

    assert exc_info.value.code == "invalid_token"


# --- admin HTTP endpoints ------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_beta_invite_and_revoke_endpoints_require_token(
    client: AsyncClient,
) -> None:
    no_token = await client.post("/admin/beta/invite", json={"github_login": "x"})
    assert no_token.status_code == 403

    ok = await client.post(
        "/admin/beta/invite",
        json={"github_login": "http-invited"},
        headers={"X-Admin-Token": "test-admin-metrics-token"},
    )
    assert ok.status_code == 200
    assert ok.json()["github_login"] == "http-invited"

    revoke = await client.post(
        "/admin/beta/revoke",
        json={"github_login": "http-invited"},
        headers={"X-Admin-Token": "test-admin-metrics-token"},
    )
    assert revoke.status_code == 200


# --- retention -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_retention_computes_d1_rate(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    cohort_start = dt.date(2026, 6, 1)
    returning = await make_user(db_session, username="returns")
    churned = await make_user(db_session, username="churns")
    db_session.add_all(
        [
            DailySession(user_id=returning.id, session_date=cohort_start, exercise_list=[]),
            DailySession(user_id=churned.id, session_date=cohort_start, exercise_list=[]),
            DailySession(
                user_id=returning.id,
                session_date=cohort_start + dt.timedelta(days=1),
                exercise_list=[],
            ),
        ],
    )
    await db_session.commit()

    response = await client.get(
        "/admin/retention",
        params={"cohort_start": cohort_start.isoformat(), "offset_days": 1},
        headers={"X-Admin-Token": "test-admin-metrics-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cohort_size"] == 2
    assert body["returned_count"] == 1
    assert body["retention_rate"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_admin_retention_requires_token(client: AsyncClient) -> None:
    response = await client.get(
        "/admin/retention",
        params={"cohort_start": "2026-06-01"},
    )
    assert response.status_code == 403


# --- empty-session rate ---------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_session_build_is_counted_in_admin_metrics(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)

    empty = await client.get("/v1/session/today", headers=auth_headers(user))
    assert empty.status_code == 200
    assert empty.json()["exercises"] == []

    metrics = await client.get(
        "/admin/metrics",
        headers={"X-Admin-Token": "test-admin-metrics-token"},
    )

    assert metrics.status_code == 200
    empty_rate = metrics.json()["empty_session_rate"]
    assert empty_rate["total"] >= 1
    assert empty_rate["errors"] >= 1


# --- job-runner health -----------------------------------------------------------


async def _wait_until(predicate, timeout_s: float = 5.0) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        if predicate():
            return True
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_admin_metrics_reports_job_runner_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOBS_ENABLED", "true")
    monkeypatch.setenv("JOB_GRADING_RETRY_INTERVAL_S", "0.05")
    monkeypatch.setenv("JOB_PERCENTILES_INTERVAL_S", "60")
    monkeypatch.setenv("JOB_PARTITIONS_INTERVAL_S", "60")
    get_settings.cache_clear()

    app = create_app()
    async with app.router.lifespan_context(app):
        scheduler: JobScheduler = app.state.job_scheduler
        ticked = await _wait_until(lambda: scheduler.run_counts["grading_retry"] >= 1)
        assert ticked, f"grading_retry never ran: {scheduler.run_counts}"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
            response = await ac.get(
                "/admin/metrics",
                headers={"X-Admin-Token": "test-admin-metrics-token"},
            )

    assert response.status_code == 200
    jobs = response.json()["jobs"]
    # A3 (D-137) registered "reminders" and "weekly_recap". They are reported
    # here with a run_count of 0 because this test leaves them on their real
    # intervals; the assertion is that /admin/metrics SEES every job.
    assert set(jobs) == {
        "grading_retry",
        "percentiles",
        "partitions",
        "reminders",
        "weekly_recap",
    }
    assert jobs["grading_retry"]["run_count"] >= 1
    assert jobs["grading_retry"]["last_run_at"] is not None


@pytest.mark.asyncio
async def test_admin_metrics_jobs_is_none_when_jobs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOBS_ENABLED", "false")
    get_settings.cache_clear()

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
            response = await ac.get(
                "/admin/metrics",
                headers={"X-Admin-Token": "test-admin-metrics-token"},
            )

    assert response.status_code == 200
    assert response.json()["jobs"] is None
