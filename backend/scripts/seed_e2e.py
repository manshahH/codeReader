"""Test-only seed for the M6 Playwright smoke test.

Not part of the production surface: creates one seeded, already-onboarded
user plus a fresh refresh token issued the same way the real OAuth callback
does (`app.auth.tokens`), and one live exercise of each type so
GET /session/today has a full spot_the_bug/trace/summarize slate to serve.

Playwright never talks to GitHub -- it sets the printed raw token as the `rt`
cookie directly (the same cookie the backend itself would have set), then
lets the SPA's normal POST /auth/refresh flow take it from there. No backend
auth code changes to support this; it's exactly the contract's cookie shape.

Requires CODEREADER_ALLOW_SEED=1 (seed content bypasses the pipeline gates
and must never reach a shared database; see scripts/seed_guard.py).

Usage: CODEREADER_ALLOW_SEED=1 python scripts/seed_e2e.py
(prints {"user_id", "username", "refresh_token"} as JSON)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.auth.tokens import generate_refresh_token, refresh_token_hash  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import create_engine, create_session_factory  # noqa: E402
from app.models import Exercise, RefreshToken, User  # noqa: E402
from scripts.seed_guard import require_seed_flag, validate_concepts  # noqa: E402
from scripts.seed_summarize_exercises import EXERCISES as SUMMARIZE_EXERCISES  # noqa: E402

_SEED_NAMESPACE = uuid.UUID("c0debee5-0000-4000-8000-0000000000e2")
# A fresh username every run (exercises stay fixed/idempotent below): each
# Playwright run needs an unattempted session, and "already_attempted today"
# is exactly the state a reused username would carry over from a prior run.
USERNAME = f"e2e-reader-{uuid.uuid4().hex[:10]}"

STB_CODE = (
    "def add_item(item, bucket=[]):\n"
    "    bucket.append(item)\n"
    "    return bucket\n"
)

TRACE_CODE = "x = [1, 2, 3]\nprint(x[1])\n"

EXERCISES = [
    dict(
        id=uuid.uuid5(_SEED_NAMESPACE, "stb-mutable-default-v1"),
        version=1,
        language="python",
        type="spot_the_bug",
        grading_mode="deterministic",
        difficulty_authored=4,
        concepts=["mutable-default-arg"],
        tags=["seed_e2e"],
        status="live",
        source={"origin": "seed_handauthored", "attribution": "e2e seed"},
        payload={
            "code": STB_CODE,
            "context_note": "Part of a cart service. Called per request.",
            "answer_mode": "line_select_plus_reason",
            "reason_options": [
                {"id": "a", "text": "Mutable default argument shared across calls"},
                {"id": "b", "text": "append returns None so the return value is wrong"},
                {"id": "c", "text": "bucket is shadowed by the parameter"},
                {"id": "d", "text": "No bug; this is correct"},
            ],
        },
        grading={
            "mode": "deterministic",
            "correct_lines": [1],
            "correct_reason_id": "a",
            "artifacts": {
                "failing_test": "assert add_item(1) == [1]",
                "sandbox_checks": {"passed": True},
            },
        },
        explanation={
            "summary": "Default arguments are evaluated once at definition time.",
            "principle": "Never use mutable default arguments.",
            "line_notes": [
                {"line": 1, "note": "bucket=[] is created once and shared across calls."},
            ],
            "verified": {"bug_lines": [1], "confirmed_by": "sandbox_execution"},
            "mismatch_flagged": False,
            "mismatch_detail": None,
        },
        est_time_s=90,
        human_reviewed=True,
    ),
    dict(
        id=uuid.uuid5(_SEED_NAMESPACE, "trace-list-index-v1"),
        version=1,
        language="python",
        type="trace",
        grading_mode="deterministic",
        difficulty_authored=3,
        concepts=["off-by-one"],
        tags=["seed_e2e"],
        status="live",
        source={"origin": "seed_handauthored", "attribution": "e2e seed"},
        payload={
            "code": TRACE_CODE,
            "context_note": "A short script.",
            "question": "What does this print?",
            "choices": [
                {"id": "a", "text": "2", "misconception": None},
                {"id": "b", "text": "1", "misconception": "off-by-one"},
                {"id": "c", "text": "3", "misconception": "off-by-one"},
                {"id": "d", "text": "IndexError", "misconception": "bounds-confusion"},
            ],
        },
        grading={
            "mode": "deterministic",
            "correct_choice_id": "a",
            "captured_stdout": "2",
            "artifacts": {"sandbox_checks": {"passed": True}},
        },
        explanation={
            "summary": "Indexing is zero-based, so x[1] is the second element, 2.",
            "principle": "List indices start at 0.",
            "trace_table": [
                {"line": 1, "state": "x = [1, 2, 3]"},
                {"line": 2, "state": "prints 2"},
            ],
            "why_wrong": [
                {"choice_id": "b", "note": "That would be x[0]."},
                {"choice_id": "c", "note": "That would be x[2]."},
                {"choice_id": "d", "note": "Index 1 is in bounds."},
            ],
            "verified": {"captured_stdout": "2", "confirmed_by": "sandbox_execution"},
            "mismatch_flagged": False,
            "mismatch_detail": None,
        },
        est_time_s=60,
        human_reviewed=True,
    ),
    SUMMARIZE_EXERCISES[0],
]


async def main() -> None:
    require_seed_flag()
    validate_concepts(EXERCISES)
    engine = create_engine()
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.username == USERNAME))
        if user is None:
            user = User(username=USERNAME, level="mid", onboarded=True)
            session.add(user)
        else:
            user.level = "mid"
            user.onboarded = True
        await session.flush()

        for spec in EXERCISES:
            existing = await session.get(Exercise, (spec["id"], spec["version"]))
            if existing is None:
                session.add(Exercise(**spec))

        raw_token = generate_refresh_token()
        now = dt.datetime.now(dt.UTC)
        session.add(
            RefreshToken(
                user_id=user.id,
                family_id=uuid.uuid4(),
                token_hash=refresh_token_hash(raw_token),
                issued_at=now,
                expires_at=now + dt.timedelta(days=get_settings().REFRESH_TOKEN_TTL_DAYS),
            ),
        )
        await session.commit()

        print(
            json.dumps(
                {"user_id": str(user.id), "username": user.username, "refresh_token": raw_token},
            ),
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
