"""M5: summarize exercises in the session sampler.

Covers the D-37 filter removal (summarize is now a normal candidate type)
and its replacement gate: docs/05 section 4's "if the LLM grader is
degraded, summarize slots are replaced at sampling time", plus extending the
M4 answer-key leak invariant to a summarize slot.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import grader_health
from app.main import create_app
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_summarize_exercise,
    make_user,
)


def _walk_keys(node: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        keys.update(node.keys())
        for value in node.values():
            keys |= _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            keys |= _walk_keys(item)
    return keys


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


@pytest.fixture
async def redis_client() -> Redis:
    redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_summarize_slot_leak_test_no_grading_or_explanation_keys(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Extends the M4 invariant-1 leak test to a summarize slot: no
    grading/explanation/rubric/reference_answer key anywhere in the wire body.
    """
    user = await make_user(db_session)
    await make_summarize_exercise(db_session, concepts=["retry-without-backoff"])

    response = await client.get("/v1/session/today", headers=auth_headers(user))

    assert response.status_code == 200
    body = response.json()
    assert len(body["exercises"]) == 1
    assert body["exercises"][0]["type"] == "summarize"
    assert body["exercises"][0]["payload"]["max_words"]

    keys = _walk_keys(body)
    assert "grading" not in keys
    assert "explanation" not in keys
    assert "rubric" not in keys
    assert "reference_answer" not in keys
    assert "must_mention" not in keys
    assert "pass_threshold" not in keys


@pytest.mark.asyncio
async def test_summarize_is_sampled_into_sessions_when_grader_is_healthy(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await make_user(db_session)
    await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    await make_summarize_exercise(db_session, concepts=["retry-without-backoff"])

    response = await client.get("/v1/session/today", headers=auth_headers(user))

    assert response.status_code == 200
    types = {ex["type"] for ex in response.json()["exercises"]}
    assert "summarize" in types


@pytest.mark.asyncio
async def test_summarize_excluded_from_new_sessions_when_grader_degraded(
    client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    user = await make_user(db_session)
    await make_stb_exercise(db_session, concepts=["mutable-default-arg"])
    await make_summarize_exercise(db_session, concepts=["retry-without-backoff"])

    for _ in range(grader_health.FAILURE_THRESHOLD):
        await grader_health.mark_failure(redis_client)
    assert await grader_health.is_degraded(redis_client) is True

    response = await client.get("/v1/session/today", headers=auth_headers(user))

    assert response.status_code == 200
    types = {ex["type"] for ex in response.json()["exercises"]}
    assert "summarize" not in types
    assert "spot_the_bug" in types
