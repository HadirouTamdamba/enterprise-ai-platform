"""Redis-backed sliding-window rate limiter with an in-memory fallback for tests."""

import time
from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings


class RateLimiter:
    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis
        self._memory: dict[str, list[float]] = {}

    async def check(self, *, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if the call is allowed, recording it in the window."""
        now = time.time()
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                pipe.zremrangebyscore(key, 0, now - window_seconds)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, window_seconds)
                results = await pipe.execute()
                return int(results[2]) <= limit
            except Exception:  # Redis down → fail open, don't take the API down
                return True
        window = self._memory.setdefault(key, [])
        window[:] = [t for t in window if t > now - window_seconds]
        window.append(now)
        return len(window) <= limit


@lru_cache
def _redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def get_rate_limiter() -> RateLimiter:
    settings = get_settings()
    if settings.environment == "test":
        return RateLimiter(redis=None)
    return RateLimiter(redis=_redis_client())
