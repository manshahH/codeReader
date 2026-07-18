"""D-123: a LIVE summarize row must never reach a session while summarize is OFF.

Found by using the app, not by a test: a summarize exercise was served in a real
local session and graded by a real LLM call. D-115 said summarize was OFF and
claimed, "verified in code", that the sampler already excluded it. It did not.
sessions/service.py chose ALL_CANDIDATE_TYPES whenever the grader was HEALTHY,
so the only thing standing between production and a summarize exercise was the
absence of live summarize content. Production had one live summarize row the
whole time.

The invariant these tests hold: SUMMARIZE_ENABLED=false means summarize cannot be
sampled REGARDLESS of what is in the exercises table. Not "there happens to be no
content", which is what the previous state actually relied on.

This matters beyond one exercise type. summarize is the only type with a
per-answer LLM cost and the only one that puts a grader on the request path,
which is the prompt-injection surface invariant 6 exists for.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.main import create_app
from app.models import Exercise
from app.sessions.sampler import ALL_CANDIDATE_TYPES, DETERMINISTIC_TYPES
from tests.factories_m4 import (
    auth_headers,
    clean_m4_tables,  # noqa: F401
    clean_redis,  # noqa: F401
    m4_env,  # noqa: F401
    make_stb_exercise,
    make_user,
)


async def make_live_summarize(session: AsyncSession) -> Exercise:
    """A LIVE summarize exercise: exactly the row that leaked into a session."""
    exercise = Exercise(
        id=uuid.uuid4(),
        version=1,
        language="python",
        type="summarize",
        grading_mode="rubric",
        difficulty_authored=4,
        concepts=["off-by-one"],
        tags=["d123"],
        status="live",
        source={"origin": "test", "attribution": "d123"},
        payload={"code": "def f(x):\n    return x\n", "context_note": "A helper."},
        grading={"mode": "rubric", "rubric_points": ["returns its argument"]},
        explanation={"summary": "Identity function.", "principle": "n/a"},
        est_time_s=90,
        human_reviewed=True,
    )
    session.add(exercise)
    await session.flush()
    await session.commit()
    return exercise


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


def test_summarize_is_off_by_default() -> None:
    """The switch itself. If this ever defaults true, the rest is theatre."""
    assert get_settings().SUMMARIZE_ENABLED is False
    assert "summarize" not in DETERMINISTIC_TYPES
    assert "summarize" in ALL_CANDIDATE_TYPES  # still buildable, just not shipped


@pytest.mark.asyncio
async def test_a_live_summarize_row_is_never_sampled_into_a_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """THE NEGATIVE THAT WAS MISSING.

    A live summarize row plus a HEALTHY grader is the exact condition that
    served one in local dev. The grader is healthy here because nothing marked
    it degraded, which is the default and was the production state too.
    """
    user = await make_user(db_session)
    summarize = await make_live_summarize(db_session)
    for concept in ("mutable-default-arg", "off-by-one", "aliasing"):
        await make_stb_exercise(db_session, concepts=[concept])

    body = (await client.get("/v1/session/today", headers=auth_headers(user))).json()

    types = [e["type"] for e in body["exercises"]]
    ids = [e["exercise_id"] for e in body["exercises"]]
    assert "summarize" not in types, f"summarize leaked into the session: {types}"
    assert str(summarize.id) not in ids
    assert body["exercises"], "the session must still be built from the other types"


@pytest.mark.asyncio
async def test_summarize_is_excluded_even_when_it_is_the_only_live_content(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The strongest form: no fallback may reach for it.

    The sampler has a degradation pad that tops a thin session up to MIN_SLOTS
    (D-61). That pad must not be a back door: with summarize as the ONLY live
    exercise, the correct outcome is an EMPTY session (D-59, transient and
    retried), never a summarize one.
    """
    user = await make_user(db_session)
    await make_live_summarize(db_session)

    body = (await client.get("/v1/session/today", headers=auth_headers(user))).json()

    assert [e["type"] for e in body["exercises"]] == []
    assert body["completed"] is False, "an empty pool is 'nothing yet', not 'done' (D-59)"


@pytest.mark.asyncio
async def test_enabling_summarize_puts_it_back_in_the_pool(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    """The positive control.

    Without this, the tests above would pass just as happily against a sampler
    that was broken for every type, and would not prove the switch is what does
    the work.
    """
    monkeypatch.setenv("SUMMARIZE_ENABLED", "true")
    get_settings.cache_clear()
    try:
        user = await make_user(db_session)
        await make_live_summarize(db_session)

        body = (await client.get("/v1/session/today", headers=auth_headers(user))).json()

        assert [e["type"] for e in body["exercises"]] == ["summarize"]
    finally:
        get_settings.cache_clear()
