from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles

from app.config.database_config import Base, engine

# from app.modules.pms.routers.room_units_routers import router as room_unit_router
from app.modules.auth.models import *
from app.modules.auth.routers.guests_router import router as guest_router
from app.modules.auth.routers.users_router import router as user_router
from app.modules.pms.models import *
from app.modules.pms.routers.properties_routers import router as property_router
from app.modules.pms.routers.room_routers import router as room_router
from app.modules.pms.routers.tenants_routers import router as tenant_router
from app.modules.pms.routers.offers_routers import router as offer_router

from app.modules.pms.routers.image_routers import router as image_router
from app.modules.pms.routers.discount_code_router import router as discount_code_router
from app.modules.pms.routers.search_router import router as search_router

from app.modules.booking.models import *
from app.utils.exception_handlers import register_exception_handlers

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # shutdown
    await engine.dispose()


app = FastAPI(
    lifespan=lifespan, title="StayEasy API", version="1.0.0", root_path="/api/v1"
)

# Default to an empty list instead of crashing on os.getenv(...).split(",")
# if ALLOWED_ORIGINS is missing from the environment.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

# Stashed on app.state so the catch-all exception handler (which runs
# outside CORSMiddleware) can attach CORS headers manually.
app.state.allowed_origins = ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(guest_router)
app.include_router(user_router)
app.include_router(tenant_router)
app.include_router(property_router)
app.include_router(room_router)
app.include_router(offer_router)
app.include_router(discount_code_router)
app.include_router(image_router)
app.include_router(search_router)


@app.get("/")
async def root():
    return {"message": "Welcome to the Easy Booking System API"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
