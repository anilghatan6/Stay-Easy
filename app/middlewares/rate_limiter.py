import time
from typing import Callable, Optional
from fastapi import Request, HTTPException, status
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


def _default_key_func(request: Request) -> str:
    """
    Identifies the caller: prefer authenticated user id (set by your auth
    middleware/dependency on request.state), fall back to client IP.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"ip:{ip}"


class RateLimiter:
    """
    Sliding-window rate limiter backed by Redis sorted sets.

    Usage as a per-route dependency:
        @router.post("/login", dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=60))])

    Different routes can use different instances with different limits —
    this is NOT a single global middleware, it's attached per-endpoint.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        key_func: Callable[[Request], str] = _default_key_func,
        scope: str = "default",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func
        self.scope = scope  # distinguishes limits on different routes for the same caller

    async def __call__(self, request: Request) -> None:
        redis_client: Optional[aioredis.Redis] = getattr(request.app.state, "redis_client", None)

        if redis_client is None:
            logger.warning("[RateLimiter] Redis unavailable — rate limiting disabled for this request")
            return  # fail open: never block traffic because the limiter itself is down

        identity = self.key_func(request)
        redis_key = f"ratelimit:{self.scope}:{identity}"

        now = time.time()
        window_start = now - self.window_seconds

        try:
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)  # drop entries outside the window
            pipe.zcard(redis_key)                              # count remaining entries
            pipe.zadd(redis_key, {str(now): now})               # record this request
            pipe.expire(redis_key, self.window_seconds)
            results = await pipe.execute()

            current_count = results[1]  # count BEFORE adding this request

            if current_count >= self.max_requests:
                # Roll back the increment for this rejected request
                await redis_client.zrem(redis_key, str(now))

                oldest = await redis_client.zrange(redis_key, 0, 0, withscores=True)
                retry_after = self.window_seconds
                if oldest:
                    retry_after = max(1, int(oldest[0][1] + self.window_seconds - now))

                logger.warning(f"[RateLimiter] Blocked '{identity}' on scope '{self.scope}' ({current_count}/{self.max_requests})")

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Please try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )

        except RedisError as e:
            logger.error(f"[RateLimiter] Redis error, failing open: {e}")
            return  # fail open — a Redis hiccup should not take down the whole API