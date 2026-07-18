"""D-119 (second half): a user is never told they are done before they are.

The reported symptom was "the dashboard says Completed at 1/5". That turned out
to be a misreading -- "1/5" is correct_count/exercise_count, so it means one
CORRECT out of five in a fully finished session, and the real defect was in
session.spec.ts, which asserted a "Session complete" screen this app has never
had. See the spec's header and D-119.

But the underlying worry was worth pinning down properly, because it is the one
version of this that WOULD be serious: a user told they are finished partway
through is a direct hit on the daily loop. These tests fix that invariant in
place for the case most likely to produce it -- a live pool too small to fill
the sampler's normal 3-to-5 slots, which is reachable in production whenever
content is thin for a level band.

The guarantee: `completed` is true only when every slot the user was actually
served has been attempted, and the served count always equals the persisted
count. A short session is fine; a dishonest one is not.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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


async def _persisted_slot_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    row = await db.execute(
        text(
            "SELECT jsonb_array_length(exercise_list) FROM daily_sessions WHERE user_id = :u",
        ),
        {"u": str(user_id)},
    )
    return int(row.scalar() or 0)


def _answer(exercise: dict) -> dict:
    return {
        "exercise_id": exercise["exercise_id"],
        "exercise_version": exercise["version"],
        "answer": {"line": 1, "reason_id": "a"},
        "time_taken_ms": 1000,
    }


@pytest.mark.asyncio
async def test_short_session_serves_exactly_what_it_persisted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """An under-filled pool must not produce a session that lies about its size.

    If the API ever served fewer exercises than daily_sessions holds slots, the
    player would run out early and the dashboard would still count the full
    slate -- which is exactly the failure the D-119 symptom was read as.
    """
    user = await make_user(db_session)
    for concept in ("mutable-default-arg", "off-by-one"):
        await make_stb_exercise(db_session, concepts=[concept])

    body = (await client.get("/v1/session/today", headers=auth_headers(user))).json()

    served = len(body["exercises"])
    assert served == 2, f"a 2-exercise pool must yield a 2-slot session, got {served}"
    assert served == await _persisted_slot_count(db_session, user.id)
    assert body["completed"] is False


@pytest.mark.asyncio
async def test_completed_stays_false_until_every_served_exercise_is_attempted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """THE NEGATIVE THAT MATTERS: no premature "you're done".

    Attempting one of two must NOT flip completed. This is the assertion that
    would have caught a real early-completion bug, and it is the reason this
    file exists even though the reported symptom turned out to be a spec bug.
    """
    user = await make_user(db_session)
    for concept in ("mutable-default-arg", "off-by-one"):
        await make_stb_exercise(db_session, concepts=[concept])
    headers = auth_headers(user)

    exercises = (await client.get("/v1/session/today", headers=headers)).json()["exercises"]
    assert len(exercises) == 2

    first = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json=_answer(exercises[0]),
    )
    assert first.status_code == 200

    midway = (await client.get("/v1/session/today", headers=headers)).json()
    assert midway["completed"] is False, "one of two attempted must NOT read as completed"
    assert [e["attempted"] for e in midway["exercises"]] == [True, False]
    assert len(midway["exercises"]) == 2, "the served slate must not shrink as it is answered"

    second = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json=_answer(exercises[1]),
    )
    assert second.status_code == 200

    done = (await client.get("/v1/session/today", headers=headers)).json()
    assert done["completed"] is True, "every served exercise attempted must read as completed"
    assert len(done["exercises"]) == 2


@pytest.mark.asyncio
async def test_a_skipped_exercise_still_counts_toward_completion(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """D-19/D-93: a skip is a submission, so it must complete the slot.

    session.spec.ts skips exactly one exercise, so if a skip did NOT count the
    session could never finish and the spec would hang until its loop bound --
    a second, independent way to produce the reported symptom.
    """
    user = await make_user(db_session)
    for concept in ("mutable-default-arg", "off-by-one"):
        await make_stb_exercise(db_session, concepts=[concept])
    headers = auth_headers(user)

    exercises = (await client.get("/v1/session/today", headers=headers)).json()["exercises"]

    skip = await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "exercise_id": exercises[0]["exercise_id"],
            "exercise_version": exercises[0]["version"],
            # The D-93 skip contract: an honest {"skipped": true} answer.
            "answer": {"skipped": True},
            "time_taken_ms": 1000,
        },
    )
    assert skip.status_code == 200, skip.text
    assert skip.json()["status"] == "skipped"

    await client.post(
        "/v1/attempts",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json=_answer(exercises[1]),
    )

    done = (await client.get("/v1/session/today", headers=headers)).json()
    assert done["completed"] is True, "a skipped slot must count as attempted (D-19)"
