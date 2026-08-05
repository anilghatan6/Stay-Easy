import time
import uuid
from typing import Callable, Optional
from fastapi import Request, HTTPException, status
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.utils.security import decode_jwt_unsafe
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

def _get_rate_limit_key(request: Request) -> str:
    """Resolves caller identity directly from Token or IP."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        payload = decode_jwt_unsafe(token)
        if payload:
            uid = payload.get("sub")
            role = payload.get("role")
            if uid:
                return f"{role}:{uid}"
                
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
        
    return f"ip:{request.client.host if request.client else '127.0.0.1'}"


class RateLimiter:
    """Sliding-window rate limiter backed by Redis sorted sets."""
    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        key_func: Callable[[Request], str] = _get_rate_limit_key,
        scope: str = "global",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func
        self.scope = scope

    async def __call__(self, request: Request) -> None:

        if getattr(request.state, f"skip_{self.scope}", False):
            return  # Bypass execution completely

        redis_client: Optional[aioredis.Redis] = getattr(
            request.app.state, "redis_client", None
        )

        if redis_client is None:
            logger.warning("[RateLimiter] Redis unavailable — rate limiting disabled")
            return  # Fail open

        identity = self.key_func(request)
        # Unique key based on target route path and distinct scope 
        redis_key = f"ratelimit:{self.scope}:{identity}:{request.url.path}"

        now = time.time()
        window_start = now - self.window_seconds
        unique_member = f"{now}:{uuid.uuid4().hex}"  # Solves the duplicate timestamp bug

        try:
            # Atomic evaluation via pipeline
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)  # Clear stale data
            pipe.zcard(redis_key)                              # Get current count
            results = await pipe.execute()
            
            current_count = results[1]

            if current_count >= self.max_requests:
                # Calculate retry time from the oldest valid record
                oldest = await redis_client.zrange(redis_key, 0, 0, withscores=True)
                retry_after = self.window_seconds
                if oldest:
                    retry_after = max(1, int(oldest[0][1] + self.window_seconds - now))

                logger.warning(f"[RateLimiter] Blocked '{identity}' on '{request.url.path}' ({current_count}/{self.max_requests})")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )

            # Request is allowed -> Log it safely to Redis
            pipe = redis_client.pipeline()
            pipe.zadd(redis_key, {unique_member: now})
            pipe.expire(redis_key, self.window_seconds)
            await pipe.execute()

        except HTTPException:
            raise  # Do not catch our own 429 exceptions
        except RedisError as e:
            logger.error(f"[RateLimiter] Redis error, failing open: {e}")
            return


def bypass_global_limit(request: Request):
    """Flags the current request to skip the global rate limiter execution."""
    request.state.skip_global_limiter = True