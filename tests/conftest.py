import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator

# ── Patch SQLite to accept PostgreSQL ARRAY columns (for schema creation) ──
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "JSON"

# ── App imports (after patch so models load cleanly) ──
from app.main import app
from app.config.database_config import Base, get_db
from app.config.redis_config import get_redis_client
from app.modules.auth.models import *   # noqa: F401,F403  registers all ORM models
from app.modules.pms.models import *    # noqa: F401,F403  registers all PMS ORM models

import fakeredis.aioredis

# ---------------------------------------------------------------------------
# In-memory SQLite engine — created once for the whole test session
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

TestingSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# (must all be session-scoped because asyncio_default_fixture_loop_scope=session)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def test_db_setup():
    """Create all tables once for the whole test session, then drop them."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def fake_redis_client():
    """A single in-memory Redis instance shared across all tests so OTPs persist."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


# ---------------------------------------------------------------------------
# Per-test DB session — a new transaction for each test, rolled back after
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_setup) -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Shared token store — plain dict passed between tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def token_store() -> dict:
    """Holds access/refresh tokens produced by login tests."""
    return {}


# ---------------------------------------------------------------------------
# HTTP client fixture — overrides FastAPI deps for every test
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def async_client(db_session, fake_redis_client) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    async def override_get_redis_client():
        yield fake_redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auto-use mock: suppress emails + pin OTP to "123456"
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_external_services(mocker):
    mocker.patch(
        "app.modules.auth.services.mail_services.send_verification_email",
        return_value=None,
    )
    mocker.patch(
        "app.modules.auth.services.mail_services.send_transactional_email",
        return_value=None,
    )
    mocker.patch(
        "app.modules.auth.services.otp_service.OTPService.generate_otp",
        return_value="123456",
    )
