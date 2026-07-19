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
    # 1. Register
    reg_payload = {
        "email": "pms_admin@example.com",
        "password": "SecurePassword123!",
        "full_name": "PMS Admin",
        "role": "admin",
        "phone": "9876543210",
    }
    resp = await client.post("/auth/users/register", json=reg_payload)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"

    # 2. Verify OTP (mock pins it to "123456")
    otp_payload = {"email": "pms_admin@example.com", "otp": "123456"}
    resp = await client.post("/auth/users/verify-otp", json=otp_payload)
    assert resp.status_code == 200, f"OTP verify failed: {resp.text}"

    # 3. Login to retrieve tokens
    login_data = {"username": "pms_admin@example.com", "password": "SecurePassword123!"}
    resp = await client.post("/auth/users/login", data=login_data)
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
            "country": "New Zealand",
            "state": "Auckland",
            "city": "Auckland City",
            "zip_code": "1010",
            "address": "123 Ocean Drive",
            "latitude": "-36.848461",
            "longitude": "174.763336",
            "hotel_detail": {
                "check_in_time_from": "2:00 PM",
                "check_in_time_to": "6:00 PM",
                "check_out_time_from": "9:00 AM",
                "check_out_time_to": "11:00 AM",
                "total_rooms": 20,
                "year_built": 2010,
                "number_of_floors": 5,
            },
            "amenities": [],
            "photo_urls": [],
        }
        resp = await pms_client.post("/pms/properties/", json=payload, headers=headers)
        assert resp.status_code == 201, f"Fixture property creation failed: {resp.text}"
        pms_token_store["property_id"] = resp.json()["data"]["id"]
    return pms_token_store["property_id"]

