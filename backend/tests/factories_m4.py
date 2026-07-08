"""Shared fixtures/helpers for M4 tests (sessions, attempts, streaks, stats).

Exercise payload/grading/explanation shapes mirror pipeline/publish.py and
pipeline/explain.py exactly so tests exercise the real contract, not a
simplified stand-in.
"""

from __future__ import annotations

import uuid

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import issue_access_token
from app.config import get_settings
from app.models import Exercise, User

TOKEN_ENC_KEY = "test-token-enc-key-32-byte-value"


@pytest.fixture(autouse=True)
def m4_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-github-client-secret")
    monkeypatch.setenv("TOKEN_ENC_KEY", TOKEN_ENC_KEY)
    monkeypatch.setenv("APP_ORIGIN", "https://app.example")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("RATE_LIMIT_ATTEMPTS_PER_MINUTE", "10")
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "10")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def clean_redis() -> None:
    redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()


@pytest.fixture(autouse=True)
async def clean_m4_tables(db_session: AsyncSession) -> None:
    """M4 request handlers commit their own transactions (session build,
    attempt submission), so the rollback-on-teardown isolation `db_session`
    normally provides doesn't apply to data created via HTTP calls in these
    tests. Truncate before each test instead. CASCADE follows every FK
    (attempts partitions included), RESTART IDENTITY resets bigint PKs.
    """
    await db_session.execute(text("TRUNCATE TABLE users, exercises RESTART IDENTITY CASCADE"))
    await db_session.commit()


async def make_user(
    session: AsyncSession,
    *,
    username: str | None = None,
    timezone: str = "UTC",
    level: str = "mid",
) -> User:
    user = User(
        username=username or f"reader-{uuid.uuid4().hex[:10]}",
        timezone=timezone,
        level=level,
    )
    session.add(user)
    await session.flush()
    await session.commit()
    return user


def auth_headers(user: User) -> dict[str, str]:
    token = issue_access_token(
        user_id=user.id,
        secret=get_settings().jwt_secrets[0],
        ttl_seconds=get_settings().ACCESS_TOKEN_TTL,
    )
    return {"Authorization": f"Bearer {token}"}


async def make_stb_exercise(
    session: AsyncSession,
    *,
    concepts: list[str],
    difficulty_authored: int = 4,
    correct_line: int = 1,
    correct_reason_id: str = "a",
    status: str = "live",
) -> Exercise:
    exercise = Exercise(
        id=uuid.uuid4(),
        version=1,
        language="python",
        type="spot_the_bug",
        grading_mode="deterministic",
        difficulty_authored=difficulty_authored,
        concepts=concepts,
        tags=[],
        status=status,
        source={"origin": "test"},
        payload={
            "code": "def add_item(item, bucket=[]):\n    bucket.append(item)\n    return bucket",
            "context_note": "Part of a cart service.",
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
            "correct_lines": [correct_line],
            "correct_reason_id": correct_reason_id,
            "artifacts": {
                "failing_test": "assert add_item(1) == [1]",
                "fixed_code_hash": "deadbeef",
                "sandbox_checks": {"passed": True},
            },
        },
        explanation={
            "summary": "Default arguments are evaluated once at definition time.",
            "principle": "Never use mutable default arguments.",
            "line_notes": [{"line": correct_line, "note": "bucket=[] is created once and shared."}],
            "verified": {"bug_lines": [correct_line], "confirmed_by": "sandbox_execution"},
            "mismatch_flagged": False,
            "mismatch_detail": None,
        },
        est_time_s=90,
        human_reviewed=True,
    )
    session.add(exercise)
    await session.flush()
    await session.commit()
    return exercise


async def make_trace_exercise(
    session: AsyncSession,
    *,
    concepts: list[str],
    difficulty_authored: int = 8,
    correct_choice_id: str = "a",
    status: str = "live",
) -> Exercise:
    exercise = Exercise(
        id=uuid.uuid4(),
        version=1,
        language="python",
        type="trace",
        grading_mode="deterministic",
        difficulty_authored=difficulty_authored,
        concepts=concepts,
        tags=[],
        status=status,
        source={"origin": "test"},
        payload={
            "code": "x = [1, 2, 3]\nprint(x[1])",
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
            "correct_choice_id": correct_choice_id,
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
    )
    session.add(exercise)
    await session.flush()
    await session.commit()
    return exercise


SUMMARIZE_CODE = (
    "import time\n\n"
    "def call_with_retry(func, max_attempts=3, backoff_base=0.5):\n"
    "    attempt = 0\n"
    "    while True:\n"
    "        try:\n"
    "            return func()\n"
    "        except (ConnectionError, TimeoutError):\n"
    "            attempt += 1\n"
    "            if attempt >= max_attempts:\n"
    "                raise\n"
    "            time.sleep(backoff_base * (2 ** attempt))\n"
)

SUMMARIZE_MUST_MENTION = [
    {"point": "retries the wrapped call with exponential backoff", "weight": 0.4},
    {"point": "only retries network-related errors", "weight": 0.3},
    {"point": "re-raises the original exception after the final attempt", "weight": 0.3},
]
SUMMARIZE_MUST_NOT_CLAIM = ["retries forever with no limit", "retries on any exception"]
SUMMARIZE_REFERENCE_ANSWER = (
    "Retries the wrapped call up to max_attempts times with exponential backoff, "
    "but only for ConnectionError/TimeoutError, then re-raises the original "
    "exception once the attempt count is exhausted."
)


async def make_summarize_exercise(
    session: AsyncSession,
    *,
    concepts: list[str],
    difficulty_authored: int = 5,
    max_words: int = 60,
    pass_threshold: float = 0.6,
    status: str = "live",
) -> Exercise:
    exercise = Exercise(
        id=uuid.uuid4(),
        version=1,
        language="python",
        type="summarize",
        grading_mode="rubric",
        difficulty_authored=difficulty_authored,
        concepts=concepts,
        tags=[],
        status=status,
        source={"origin": "test"},
        payload={
            "code": SUMMARIZE_CODE,
            "context_note": "A helper used to call flaky network functions.",
            "max_words": max_words,
        },
        grading={
            "mode": "rubric",
            "rubric": {
                "must_mention": SUMMARIZE_MUST_MENTION,
                "must_not_claim": SUMMARIZE_MUST_NOT_CLAIM,
                "pass_threshold": pass_threshold,
            },
            "reference_answer": SUMMARIZE_REFERENCE_ANSWER,
        },
        explanation={
            "summary": "A retry wrapper with backoff, scoped to network errors.",
            "principle": "Retries should be bounded and scoped to transient failures.",
        },
        est_time_s=90,
        human_reviewed=True,
    )
    session.add(exercise)
    await session.flush()
    await session.commit()
    return exercise
