from dotenv import load_dotenv

import asyncio
from contextlib import asynccontextmanager
import redis.asyncio as aioredis

from fastapi import FastAPI, Depends
from app.config.database_config import engine
from app.modules.auth.models import *
from app.modules.auth.routers.guests_router import router as guest_router
from app.modules.auth.routers.users_router import router as user_router
from app.modules.auth.routers.login_router import router as login_router
from app.modules.auth.routers.password_reset_router import (
    router as password_reset_router,
)
from app.modules.pms.models import *
from app.modules.pms.routers.properties_routers import router as property_router
from app.modules.pms.routers.room_routers import router as room_router
from app.modules.pms.routers.tenants_routers import router as tenant_router
from app.modules.pms.routers.offers_routers import router as offer_router

from app.modules.pms.routers.image_routers import router as image_router
from app.modules.pms.routers.discount_code_router import router as discount_code_router
from app.modules.pms.routers.search_router import router as search_router

from app.modules.booking.models import *
from app.modules.booking.routers.booking_router import router as booking_router

from app.modules.staff_mgmt.models import *
from app.modules.staff_mgmt.routers.staffs_router import router as staff_router
from app.middlewares.cors import configure_cors
from app.utils.exception_handlers import register_exception_handlers
from app.utils.expiry_loop import _expire_stale_bookings_loop

from app.middlewares.rate_limiter import RateLimiter
from app.config.redis_config import redis_pool
from app.utils.logging import LoggerFactory

load_dotenv()

logger = LoggerFactory.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # async with engine.begin() as conn:
    # await conn.run_sync(Base.metadata.create_all)
    app.state.redis_client = aioredis.Redis(connection_pool=redis_pool)

    stop_event = asyncio.Event()
    expiry_task = asyncio.create_task(_expire_stale_bookings_loop(stop_event))

    yield

    stop_event.set()
    await expiry_task
    await app.state.redis_client.close()
    await redis_pool.disconnect()
    await engine.dispose()


global_limiter = RateLimiter(max_requests=150, window_seconds=60, scope="global")

app = FastAPI(
    lifespan=lifespan,
    title="StayEasy API",
    version="1.0.0",
    root_path="/api/v1",
    dependencies=[Depends(global_limiter)],
)


register_exception_handlers(app)

configure_cors(app)

# ── Inner layer: Routes ──
app.include_router(guest_router)
app.include_router(user_router)
app.include_router(login_router)
app.include_router(password_reset_router)
app.include_router(tenant_router)
app.include_router(property_router)
app.include_router(room_router)
app.include_router(offer_router)
app.include_router(discount_code_router)
app.include_router(staff_router)
app.include_router(image_router)
app.include_router(search_router)
app.include_router(booking_router)


@app.get("/")
async def root():
    return {"message": "Welcome to the Easy Booking System API"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
