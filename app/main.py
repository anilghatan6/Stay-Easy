import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from app.config.database_config import Base, engine

from app.modules.auth.models import *
from app.modules.auth.routers.guests_router import router as guest_router
from app.modules.auth.routers.users_router import router as user_router
from app.modules.auth.routers.login_router import router as login_router
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
from app.utils.cors import configure_cors
from app.utils.exception_handlers import register_exception_handlers
from app.utils.expiry_loop import _expire_stale_bookings_loop
from app.utils.logging import LoggerFactory

load_dotenv()

logger = LoggerFactory.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stop_event = asyncio.Event()
    expiry_task = asyncio.create_task(_expire_stale_bookings_loop(stop_event))

    yield

    stop_event.set()
    await expiry_task
    await engine.dispose()


app = FastAPI(
    lifespan=lifespan, title="StayEasy API", version="1.0.0", root_path="/api/v1"
)

register_exception_handlers(app)

configure_cors(app)

# ── Inner layer: Routes ──
app.include_router(guest_router)
app.include_router(user_router)
app.include_router(login_router)
app.include_router(tenant_router)
app.include_router(property_router)
app.include_router(room_router)
app.include_router(offer_router)
app.include_router(discount_code_router)
app.include_router(image_router)
app.include_router(search_router)
app.include_router(booking_router)


@app.get("/")
async def root():
    return {"message": "Welcome to the Easy Booking System API"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
