"""/healthz checks (D-146).

The DEFAULT here runs IN-PROCESS via ASGITransport, exactly like every other
HTTP test in the suite, so a bare `pytest` is green on any machine that has the
Postgres and Redis the rest of the suite already needs. It is NOT a weaker check
than hitting a live server: /healthz's body runs `_check_postgres` and
`_check_redis` against the configured services either way, and the negative test
below proves those probes actually fire (a down dependency yields 503, not a
false 200). The only thing a live server would additionally prove is that a
uvicorn process is up and serving, which is a DEPLOY concern, not app behaviour;
that variant still exists, behind an explicit opt-in (see the bottom of this
file), so it is not lost.

Before D-146 the default was inverted: it connected to a real server on :8000
and CI set HEALTHZ_TEST_IN_PROCESS=1 to get the in-process path. That made the
one test in an otherwise-green suite fail on a normal dev machine -- the exact
kind of always-red test developers learn to ignore (D-128).
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# DATABASE_URL and REDIS_URL already point at this run's isolated database and
# Redis logical DB (conftest, D-88 + D-147); the in-process app checks THOSE,
# which is what makes the in-process probe real rather than a stand-in. Only the
# non-service secrets Settings needs to construct are supplied here.
_SETTINGS_SECRETS = {
    "JWT_SECRET": "test-jwt-secret",
    "GITHUB_CLIENT_SECRET": "test-github-client-secret",
    "TOKEN_ENC_KEY": "test-token-encryption-key-32b",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
}

# The live-server variant is a DEPLOY smoke test, not a unit. It stays in the
# suite but is opt-in: set HEALTHZ_TEST_AGAINST_SERVER=1 (and have a server on
# :8000) to run it. `bin/verify-deploy` and the Playwright CI job, which both
# already start a real server, are its natural homes.
_LIVE_SERVER_FLAG = "HEALTHZ_TEST_AGAINST_SERVER"


async def _in_process_healthz(monkeypatch: pytest.MonkeyPatch) -> "object":
    from app.config import get_settings
    from app.main import create_app

    for key, value in _SETTINGS_SECRETS.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    get_settings.cache_clear()
    return response


@pytest.mark.asyncio
async def test_healthz_ok_in_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default a bare `pytest` runs: in-process against this run's real
    Postgres and Redis. Green on any dev machine with the documented services
    up, no env var required."""
    response = await _in_process_healthz(monkeypatch)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_healthz_reports_a_down_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative (house rule), and the proof the in-process swap is not a
    weakening: point REDIS_URL at a dead port and /healthz must actually run
    `_check_redis`, fail it, and report 503 with redis named -- not a hollow
    200. A check that could not go red would not be a check."""
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    response = await _in_process_healthz(monkeypatch)
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert "redis" in body["dependencies"]


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv(_LIVE_SERVER_FLAG) != "1",
    reason=f"deploy smoke test; set {_LIVE_SERVER_FLAG}=1 with a server on :8000 to run it",
)
async def test_healthz_against_a_live_server() -> None:
    """Opt-in DEPLOY check: a real uvicorn process is up and serving /healthz.
    Distinct from app behaviour, which the in-process tests already cover."""
    async with AsyncClient(base_url="http://127.0.0.1:8000") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
