from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after)
        return headers


_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = 1
local rate = limit / window
local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
  tokens = limit
  ts = now
end
local delta = math.max(0, now - ts)
tokens = math.min(limit, tokens + (delta * rate))
local allowed = 0
local retry_after = 0
if tokens >= cost then
  allowed = 1
  tokens = tokens - cost
else
  retry_after = math.ceil((cost - tokens) / rate)
end
redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(window * 2))
return {allowed, math.floor(tokens), retry_after}
"""


async def check_token_bucket(
    redis: Redis,
    *,
    key: str,
    limit: int,
    window_seconds: int = 60,
) -> RateLimitResult:
    redis_time = await redis.time()
    now = int(redis_time[0])
    allowed, remaining, retry_after = await redis.eval(
        _TOKEN_BUCKET_SCRIPT,
        1,
        key,
        limit,
        window_seconds,
        now,
    )
    return RateLimitResult(
        allowed=bool(allowed),
        limit=limit,
        remaining=max(0, int(remaining)),
        retry_after=max(1, int(retry_after)),
    )