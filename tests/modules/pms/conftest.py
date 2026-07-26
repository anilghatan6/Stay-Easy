"""
PMS-level conftest.py
Provides session-scoped fixtures shared by ALL pms test modules:
  - pms_token_store   : carries tokens + created resource IDs between tests
  - pms_client        : async HTTP client pre-authenticated as an admin user with a tenant
  - registered_user   : registers + verifies an admin user once
  - user_with_tenant  : builds on registered_user to also create a tenant
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

# ────────────────────────────────────────────────────────────────────────────
# Shared mutable state (session-scoped plain dict)
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def pms_token_store() -> dict:
    """
    Carries access/refresh tokens and created resource IDs
    (tenant_id, property_id, room_id, offer_id) between tests.
    """
    return {}


# ────────────────────────────────────────────────────────────────────────────
# Re-usable auth helpers
# ────────────────────────────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, store: dict) -> None:
    """Register → verify OTP → login and persist tokens in *store*."""
    # 1. Register (skip if already exists from another module in the same session)
    reg_payload = {
        "email": "pms_admin@example.com",
        "password": "SecurePassword123!",
        "full_name": "PMS Admin",
        "role": "admin",
        "phone": "9876543210",
    }
    resp = await client.post("/auth/users/register", json=reg_payload)
    if resp.status_code == 409 or "already exists" in resp.text:
        pass  # user already registered by another module
    else:
        assert resp.status_code == 201, f"Registration failed: {resp.text}"

    # 2. Verify OTP (mock pins it to "123456") — skip if already verified
    otp_payload = {"email": "pms_admin@example.com", "otp": "123456"}
    resp = await client.post("/auth/users/verify-otp", json=otp_payload)
    if resp.status_code != 200:
        pass  # already verified

    # 3. Login to retrieve tokens
    login_data = {"username": "pms_admin@example.com", "password": "SecurePassword123!"}
    resp = await client.post("/auth/login", data=login_data)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    store["access_token"] = data["access_token"]
    store["refresh_token"] = data["refresh_token"]


async def _create_tenant(client: AsyncClient, store: dict) -> None:
    """Create a tenant for the authenticated user and persist tenant_id."""
    headers = {"Authorization": f"Bearer {store['access_token']}"}
    tenant_payload = {
        "name": "PMS Test Hotel",
        "currency": "USD",
        "timezone": "UTC",
    }
    resp = await client.post("/tenants/", json=tenant_payload, headers=headers)
    assert resp.status_code == 201, f"Tenant creation failed: {resp.text}"
    store["tenant_id"] = resp.json()["data"]["id"]


# ────────────────────────────────────────────────────────────────────────────
# Session-scoped HTTP client with auth + tenant already set up
# ────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def pms_client(async_client: AsyncClient, pms_token_store: dict):
    """
    Async HTTP client that is already authenticated (admin role) and
    has a tenant created.  The underlying `async_client` fixture from the
    root conftest.py handles DB/Redis overrides.
    """
    # Only register & login & create tenant if not already done in the session
    if "access_token" not in pms_token_store:
        await _register_and_login(async_client, pms_token_store)
        await _create_tenant(async_client, pms_token_store)
    yield async_client


@pytest_asyncio.fixture(scope="function")
async def pms_property_id(pms_client: AsyncClient, pms_token_store: dict) -> str:
    """
    Ensures a property is created and returns its ID.
    Caches it in pms_token_store so subsequent tests in the session reuse it.
    """
    if "property_id" not in pms_token_store:
        headers = {"Authorization": f"Bearer {pms_token_store['access_token']}"}
        payload = {
            "name": "Fixture Hotel",
            "type": "HOTEL",
            "description": "Hotel created by fixture.",
            "phone_number": "1234567890",
            "email": "fixture@hotel.com",
            "total_rooms": 20,
            "year_built": 2010,
            "number_of_floors": 5,
        }
        resp = await pms_client.post(
            "/properties/general-information", json=payload, headers=headers
        )
        assert resp.status_code == 201, f"Fixture property creation failed: {resp.text}"
        pms_token_store["property_id"] = resp.json()["data"]["id"]
    return pms_token_store["property_id"]

