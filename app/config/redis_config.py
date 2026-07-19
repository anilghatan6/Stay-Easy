import redis.asyncio as aioredis
from typing import AsyncGenerator
from dotenv import load_dotenv
import os

load_dotenv()

# Create a global connection pool
redis_pool = aioredis.ConnectionPool.from_url(
    os.getenv("REDIS_URL"),
    decode_responses=True,  # Automatically decodes byte responses to Python strings
)


async def get_redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """
    FastAPI dependency to inject the Redis client into your routes.
    """
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.close()
