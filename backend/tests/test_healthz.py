import os

import pytest
from httpx import ASGITransport, AsyncClient


async def _get_in_process_healthz(monkeypatch: pytest.MonkeyPatch):
    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv(
        "DATABASE_URL",
        os.getenv(
            "DATABASE_URL",
            "postgresql://codereader:codereader@127.0.0.1:5432/codereader",
        ),
    )
    monkeypatch.setenv("REDIS_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    monkeypatch.setenv("JWT_SECRET", os.getenv("JWT_SECRET", "test-jwt-secret"))
    monkeypatch.setenv(
        "GITHUB_CLIENT_SECRET",
        os.getenv("GITHUB_CLIENT_SECRET", "test-github-secret"),
    )
    monkeypatch.setenv(
        "TOKEN_ENC_KEY",
        os.getenv("TOKEN_ENC_KEY", "test-token-encryption-key-32b"),
    )
    monkeypatch.setenv(
        "ANTHROPIC_API_KEY",
        os.getenv("ANTHROPIC_API_KEY", "test-anthropic-key"),
    )
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    get_settings.cache_clear()
    return response


async def _get_compose_healthz():
    async with AsyncClient(base_url="http://127.0.0.1:8000") as client:
        return await client.get("/healthz")


@pytest.mark.asyncio
async def test_healthz_returns_ok_against_services(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.getenv("HEALTHZ_TEST_IN_PROCESS") == "1":
        response = await _get_in_process_healthz(monkeypatch)
    else:
        response = await _get_compose_healthz()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}