from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_dispute_opens_for_a_live_exercise(client: AsyncClient, db_session) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)

    response = await client.post(
        f"/v1/exercises/{exercise.id}/v/{exercise.version}/dispute",
        headers=headers,
        json={
            "reason": "wrong_answer",
            "body": "Line 4 also changes behavior.",
            "attempt_id": None,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert isinstance(body["dispute_id"], int)


@pytest.mark.asyncio
async def test_second_open_dispute_from_same_user_conflicts(
    client: AsyncClient,
    db_session,
) -> None:
    user = await make_user(db_session)
    exercise = await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    headers = auth_headers(user)

    first = await client.post(
        f"/v1/exercises/{exercise.id}/v/{exercise.version}/dispute",
        headers=headers,
        json={"reason": "ambiguous", "body": None, "attempt_id": None},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/v1/exercises/{exercise.id}/v/{exercise.version}/dispute",
        headers=headers,
        json={"reason": "other", "body": None, "attempt_id": None},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_dispute_on_unknown_exercise_is_not_found(client: AsyncClient, db_session) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user)

    response = await client.post(
        f"/v1/exercises/{uuid.uuid4()}/v/1/dispute",
        headers=headers,
        json={"reason": "other", "body": None, "attempt_id": None},
    )
    assert response.status_code == 404
