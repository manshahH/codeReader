from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_user,
)


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_patch_me_sets_level_and_marks_onboarded(client: AsyncClient, db_session) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)

    me_before = await client.get("/v1/me", headers=headers)
    assert me_before.json()["user"]["onboarded"] is False

    response = await client.patch("/v1/me", headers=headers, json={"level": "senior"})

    assert response.status_code == 200
    body = response.json()["user"]
    assert body["level"] == "senior"
    assert body["onboarded"] is True


@pytest.mark.asyncio
async def test_patch_me_rejects_invalid_timezone(client: AsyncClient, db_session) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)

    response = await client.patch("/v1/me", headers=headers, json={"timezone": "Not/AZone"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_patch_me_rejects_invalid_level(client: AsyncClient, db_session) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)

    response = await client.patch("/v1/me", headers=headers, json={"level": "expert"})

    assert response.status_code == 400
