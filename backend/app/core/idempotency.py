"""POST /attempts idempotency (D-8): Redis-only, 24h TTL, not a DB constraint."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

DEFAULT_TTL_SECONDS = 24 * 60 * 60
RESERVATION_TTL_SECONDS = 30
_WAIT_POLL_INTERVAL_SECONDS = 0.1


def request_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdempotencyRecord:
    request_hash: str
    status_code: int
    body: dict[str, Any]


def _key(namespace: str, idempotency_key: str) -> str:
    return f"idem:{namespace}:{idempotency_key}"


async def get_cached(
    redis: Redis,
    *,
    namespace: str,
    idempotency_key: str,
) -> IdempotencyRecord | None:
    raw = await redis.get(_key(namespace, idempotency_key))
    if raw is None:
        return None
    data = json.loads(raw)
    return IdempotencyRecord(
        request_hash=data["request_hash"],
        status_code=data["status_code"],
        body=data["body"],
    )


async def store(
    redis: Redis,
    *,
    namespace: str,
    idempotency_key: str,
    request_hash: str,
    status_code: int,
    body: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    payload = json.dumps(
        {"request_hash": request_hash, "status_code": status_code, "body": body},
        default=str,
    )
    await redis.set(_key(namespace, idempotency_key), payload, ex=ttl_seconds)


def _reservation_key(namespace: str, idempotency_key: str) -> str:
    return f"idem:lock:{namespace}:{idempotency_key}"


async def acquire_reservation(
    redis: Redis,
    *,
    namespace: str,
    idempotency_key: str,
    ttl_seconds: int = RESERVATION_TTL_SECONDS,
) -> bool:
    """SET NX reservation on an idempotency key (concurrency fix, M7 audit).

    Two concurrent requests carrying the SAME Idempotency-Key (a network
    retry racing the still-in-flight original) previously both missed the
    cache (nothing had been stored yet) and ran the full request
    independently -- a duplicate attempt row, a duplicate stats update.
    Whoever wins this SET NX proceeds; the loser calls `wait_for_cached`
    instead of racing ahead, so it returns the winner's actual response as
    a byte-identical replay rather than colliding with it downstream.
    """
    return bool(
        await redis.set(_reservation_key(namespace, idempotency_key), "1", nx=True, ex=ttl_seconds),
    )


async def release_reservation(redis: Redis, *, namespace: str, idempotency_key: str) -> None:
    await redis.delete(_reservation_key(namespace, idempotency_key))


async def wait_for_cached(
    redis: Redis,
    *,
    namespace: str,
    idempotency_key: str,
    timeout_seconds: float,
) -> IdempotencyRecord | None:
    """Polls for the in-flight winner's stored result. Returns None on
    timeout (the winner crashed or is abnormally slow) -- the caller falls
    through to normal processing in that case; whatever data-integrity
    guard exists downstream (e.g. a DB advisory lock) is the real backstop.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while True:
        record = await get_cached(redis, namespace=namespace, idempotency_key=idempotency_key)
        if record is not None:
            return record
        if loop.time() >= deadline:
            return None
        await asyncio.sleep(_WAIT_POLL_INTERVAL_SECONDS)
