"""POST /attempts idempotency (D-8): Redis-only, 24h TTL, not a DB constraint."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

DEFAULT_TTL_SECONDS = 24 * 60 * 60


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
