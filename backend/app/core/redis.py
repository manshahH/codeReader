from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from redis.asyncio import Redis

from app.config import get_settings


async def get_redis(request: Request) -> AsyncIterator[Redis]:
    client = getattr(request.app.state, "redis", None)
    if client is None:
        client = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()
        return
    yield client