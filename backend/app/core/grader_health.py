"""Circuit-breaker-lite signal for LLM grader health (docs/05 section 4: "if
the LLM grader is degraded, summarize slots are replaced at sampling time").

Redis-only, self-healing via TTL -- this is a disposable operational signal,
not state anything else depends on, so it doesn't warrant a table or a
health-check endpoint of its own (LLM provider health is reported in
metrics, per docs/05 section 7, not in /healthz).
"""

from __future__ import annotations

from redis.asyncio import Redis

_STREAK_KEY = "grader:failure_streak"
_DEGRADED_KEY = "grader:degraded"

FAILURE_THRESHOLD = 3
DEGRADED_TTL_SECONDS = 5 * 60


async def mark_success(redis: Redis) -> None:
    await redis.delete(_STREAK_KEY, _DEGRADED_KEY)


async def mark_failure(redis: Redis) -> None:
    streak = await redis.incr(_STREAK_KEY)
    await redis.expire(_STREAK_KEY, DEGRADED_TTL_SECONDS)
    if streak >= FAILURE_THRESHOLD:
        await redis.set(_DEGRADED_KEY, "1", ex=DEGRADED_TTL_SECONDS)


async def is_degraded(redis: Redis) -> bool:
    return bool(await redis.exists(_DEGRADED_KEY))
