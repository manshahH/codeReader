"""Minimal golden-signals collection (M7 observability).

Redis-backed, best-effort, disposable -- like grader_health.py, this is an
operational signal, not state anything else depends on. Latencies are kept
as a bounded rolling sample (not a full histogram) so p95 is a sort over a
few hundred floats, cheap enough to compute on every /admin/metrics poll.
"""

from __future__ import annotations

import math

from redis.asyncio import Redis

_LATENCY_SAMPLE_MAX = 500


def _latency_key(metric: str) -> str:
    return f"metrics:latency:{metric}"


def _counter_key(metric: str, kind: str) -> str:
    return f"metrics:count:{metric}:{kind}"


async def record_latency(redis: Redis, metric: str, duration_ms: float) -> None:
    key = _latency_key(metric)
    await redis.lpush(key, duration_ms)
    await redis.ltrim(key, 0, _LATENCY_SAMPLE_MAX - 1)


async def p95_latency_ms(redis: Redis, metric: str) -> float | None:
    values = await redis.lrange(_latency_key(metric), 0, -1)
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    index = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


async def record_outcome(redis: Redis, metric: str, *, is_error: bool) -> None:
    await redis.incr(_counter_key(metric, "total"))
    if is_error:
        await redis.incr(_counter_key(metric, "errors"))


async def error_rate(redis: Redis, metric: str) -> dict[str, float | int]:
    total_raw, errors_raw = await redis.mget(
        _counter_key(metric, "total"),
        _counter_key(metric, "errors"),
    )
    total = int(total_raw or 0)
    errors = int(errors_raw or 0)
    return {
        "total": total,
        "errors": errors,
        "error_rate": (errors / total) if total else 0.0,
    }
