"""The external job trigger for a scale-to-zero platform (D-138).

Every gate has a negative, per CLAUDE.md.
"""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import create_engine, create_session_factory
from app.jobs.trigger import run_jobs
from tests.factories_m4 import (  # noqa: F401
    clean_m4_tables,
    clean_redis,
    m4_env,
    make_user,
)


@pytest.fixture(autouse=True)
def admin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_METRICS_TOKEN", "test-admin-metrics-token")
    # The trigger must not need the in-process scheduler: the whole point is
    # that it works when the scheduler is absent.
    monkeypatch.setenv("JOBS_ENABLED", "false")
    get_settings.cache_clear()


@pytest.fixture
async def app_client() -> AsyncClient:
    from app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://testserver") as client:
            yield client


@pytest.fixture
async def redis_client() -> Redis:
    client = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def _post(client: AsyncClient, token: str | None = "test-admin-metrics-token", **kw):
    headers = {"X-Admin-Token": token} if token else {}
    return await client.post("/admin/jobs/run", headers=headers, **kw)


@pytest.mark.asyncio
async def test_trigger_runs_both_jobs_without_the_in_process_scheduler(
    app_client: AsyncClient,
) -> None:
    """The load-bearing property: JOBS_ENABLED is false, so nothing is ticking
    on its own, and the jobs still run."""
    response = await _post(app_client, json={})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"reminders", "weekly_recap"}
    # Real sweep results, not a stub acknowledgement.
    assert "considered" in body["reminders"]
    assert "considered" in body["weekly_recap"]


@pytest.mark.asyncio
async def test_trigger_can_run_one_named_job(app_client: AsyncClient) -> None:
    response = await _post(app_client, json={"jobs": ["reminders"]})

    assert response.status_code == 200
    assert set(response.json()) == {"reminders"}


@pytest.mark.asyncio
async def test_trigger_rejects_an_unknown_job(app_client: AsyncClient) -> None:
    """NEGATIVE. The name is an allowlist, not a lookup into whatever exists:
    grading_retry/percentiles/partitions are deliberately not triggerable."""
    response = await _post(app_client, json={"jobs": ["percentiles"]})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_trigger_requires_the_admin_token(app_client: AsyncClient) -> None:
    """NEGATIVE. An unauthenticated caller must not be able to make us send."""
    response = await _post(app_client, token=None, json={})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_trigger_rejects_a_wrong_admin_token(app_client: AsyncClient) -> None:
    """NEGATIVE."""
    response = await _post(app_client, token="not-the-token", json={})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_trigger_is_404_when_no_admin_token_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NEGATIVE. An unconfigured deploy must not quietly expose a way to make
    the app send email. 404 rather than 403, so it does not confirm the route."""
    monkeypatch.setenv("ADMIN_METRICS_TOKEN", "")
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://testserver") as client:
            response = await client.post("/admin/jobs/run", json={})

    assert response.status_code == 404
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_an_overlapping_trigger_does_not_run_the_job_twice(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    """A delayed trigger landing on a running one reports already_running
    rather than paying for a second full sweep.

    Correctness never depended on this -- claim_period's primary key already
    makes concurrent sweeps unable to double-send -- so the lock is a waste
    guard. It is tested anyway because "it is only an optimisation" is how an
    optimisation silently stops working.
    """
    engine = create_engine()
    factory = create_session_factory(engine)
    try:
        # Simulate a run in flight by taking the lock the endpoint takes.
        await redis_client.set("jobtrigger:running:reminders", "1", ex=600, nx=True)

        result = await run_jobs(factory, redis_client, names=["reminders"])

        assert result["reminders"] == {"skipped": "already_running"}
    finally:
        await redis_client.delete("jobtrigger:running:reminders")
        await engine.dispose()


@pytest.mark.asyncio
async def test_the_lock_is_released_so_the_next_trigger_runs(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    """NEGATIVE of the above: a completed run must not leave the lock behind,
    or the job silently stops until the TTL expires."""
    engine = create_engine()
    factory = create_session_factory(engine)
    try:
        first = await run_jobs(factory, redis_client, names=["reminders"])
        second = await run_jobs(factory, redis_client, names=["reminders"])

        assert "considered" in first["reminders"]
        assert "considered" in second["reminders"]
        assert await redis_client.get("jobtrigger:running:reminders") is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_one_failing_job_does_not_stop_the_other(
    db_session: AsyncSession, redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Isolation, matching JobScheduler's. The error is reported as a TYPE,
    never a message: these run against user data."""
    import app.jobs.trigger as trigger

    async def boom(_factory):
        raise RuntimeError("dev@example.com blew up")

    monkeypatch.setitem(trigger.TRIGGERABLE, "reminders", boom)
    engine = create_engine()
    factory = create_session_factory(engine)
    try:
        result = await run_jobs(factory, redis_client)

        assert result["reminders"] == {"error": "RuntimeError"}
        # The message, which carried an address, is not in the response.
        assert "dev@example.com" not in str(result)
        assert "considered" in result["weekly_recap"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_triggered_reminders_actually_send(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    """End to end through the HTTP route with a real due user: the trigger is
    the only clock here, and a reminder still goes out."""
    user = await make_user(db_session)
    user.email = "due@example.com"
    user.email_verified_at = dt.datetime.now(dt.UTC)
    user.reminder_local_time = dt.time(0, 1)
    await db_session.commit()

    response = await _post(app_client, json={"jobs": ["reminders"]})

    assert response.status_code == 200
    assert response.json()["reminders"]["sent"] == 1


class _DeadRedis:
    """Redis is unreachable. Every call raises, including the release."""

    async def set(self, *args, **kwargs):
        raise ConnectionError("redis is down")

    async def delete(self, *args, **kwargs):
        raise ConnectionError("redis is down")


class _RedisDiesMidRun:
    """The lock is taken, then Redis goes away before the release."""

    def __init__(self) -> None:
        self.released = False

    async def set(self, *args, **kwargs):
        return True

    async def delete(self, *args, **kwargs):
        self.released = True
        raise ConnectionError("redis went away")


@pytest.mark.asyncio
async def test_jobs_still_run_when_redis_is_unavailable(db_session: AsyncSession) -> None:
    """A WASTE GUARD MUST NOT BECOME A HARD DEPENDENCY.

    The lock exists to stop a delayed trigger paying for a duplicate sweep. It
    is not what makes overlap safe -- claim_period's primary key is. So a Redis
    outage must degrade to "run unlocked", never to "do not send". Letting it
    fail would make reminders depend on the one component the design explicitly
    says they do not depend on.
    """
    engine = create_engine()
    factory = create_session_factory(engine)
    try:
        result = await run_jobs(factory, _DeadRedis(), names=["reminders"])

        # A real sweep ran, not an error and not a skip.
        assert "considered" in result["reminders"]
        assert "error" not in result["reminders"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_redis_dying_mid_run_does_not_discard_a_successful_sweep(
    db_session: AsyncSession,
) -> None:
    """NEGATIVE of the above, at the other end: the release is best-effort too.

    Raising on cleanup would throw away a sweep that already succeeded, and the
    TTL releases the lock anyway.
    """
    engine = create_engine()
    factory = create_session_factory(engine)
    dying = _RedisDiesMidRun()
    try:
        result = await run_jobs(factory, dying, names=["reminders"])

        assert dying.released is True
        assert "considered" in result["reminders"]
    finally:
        await engine.dispose()
