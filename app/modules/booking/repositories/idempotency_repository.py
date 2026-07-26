import json
import redis.asyncio as aioredis
from app.utils.exceptions import RedisException


PROCESSING_TTL_SECONDS = 600  # 10 minutes for the processing lock
RESULT_TTL_SECONDS = 86400    # 24 hours for cached results


class IdempotencyRepository:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def try_reserve(self, key: str) -> bool:
        try:
            reserved = await self.redis.set(
                f"idempotency:{key}", "processing", nx=True, ex=PROCESSING_TTL_SECONDS
            )
            return bool(reserved)
        except Exception as e:
            raise RedisException(user_message="Unable to process request", internal_detail=str(e))

    async def get_result(self, key: str) -> dict | None:
        try:
            raw = await self.redis.get(f"idempotency:{key}")
            if raw is None or raw == "processing":
                return None
            return json.loads(raw)
        except Exception as e:
            raise RedisException(user_message="Unable to process request", internal_detail=str(e))

    async def save_result(self, key: str, response_body: dict):
        try:
            serialized = json.dumps(response_body, default=str)
            await self.redis.set(
                f"idempotency:{key}", serialized, ex=RESULT_TTL_SECONDS
            )
        except Exception as e:
            raise RedisException(user_message="Unable to process request", internal_detail=str(e))

    async def release(self, key: str):
        try:
            await self.redis.delete(f"idempotency:{key}")
        except Exception as e:
            raise RedisException(user_message="Unable to process request", internal_detail=str(e))
