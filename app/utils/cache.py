import json
import hashlib
from typing import Optional, Any
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


def build_cache_key(prefix: str, **params: Any) -> str:
    """
    Builds a deterministic, order-independent cache key from arbitrary params.

    Raises:
        ValueError: if prefix is empty, or params contain non-serializable values.
    """
    if not prefix or not prefix.strip():
        raise ValueError("Cache key prefix cannot be empty")

    try:
        normalized = json.dumps(params, sort_keys=True, default=str)
    except (TypeError, ValueError) as e:
        logger.error(f"[Cache] Failed to serialize params for key '{prefix}': {e}")
        raise ValueError(f"Cannot build cache key: unserializable params — {e}") from e

    hash_suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{hash_suffix}"


async def get_cached(redis_client: aioredis.Redis, key: str) -> Optional[Any]:
    """
    Retrieves and deserializes a cached value.
    Fails open: any error (Redis down, corrupted data) returns None (cache miss)
    rather than raising, so the caller always falls through to a normal DB read.
    """
    if redis_client is None:
        return None

    try:
        raw = await redis_client.get(key)
        if raw is None:
            return None

        return json.loads(raw)

    except RedisError as e:
        logger.error(f"[Cache] Redis error reading key '{key}': {e}")
        return None
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"[Cache] Corrupted cache data for key '{key}': {e}")
        # Best-effort cleanup of the bad entry — don't let a corrupted key persist
        try:
            await redis_client.delete(key)
        except RedisError:
            pass
        return None
    except Exception as e:
        logger.error(f"[Cache] Unexpected error reading key '{key}': {e}")
        return None


async def set_cached(
    redis_client: aioredis.Redis,
    key: str,
    value: Any,
    ttl_seconds: int,
) -> bool:
    """
    Serializes and stores a value with a TTL.
    Fails open: returns False on any error, never raises — a failed cache
    write must never fail the actual request.
    """
    if redis_client is None:
        return False

    if ttl_seconds <= 0:
        logger.warning(f"[Cache] Skipping cache write for '{key}': non-positive TTL ({ttl_seconds})")
        return False

    try:
        serialized = json.dumps(value, default=str)
    except (TypeError, ValueError) as e:
        logger.error(f"[Cache] Failed to serialize value for key '{key}': {e}")
        return False

    try:
        await redis_client.set(key, serialized, ex=ttl_seconds)
        return True
    except RedisError as e:
        logger.error(f"[Cache] Redis error writing key '{key}': {e}")
        return False
    except Exception as e:
        logger.error(f"[Cache] Unexpected error writing key '{key}': {e}")
        return False