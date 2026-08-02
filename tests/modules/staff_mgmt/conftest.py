"""
Staff-management level conftest.py

Provides shared fixtures used by ALL staff_mgmt tests:
  - staff_token_store  : carries tokens + created resource IDs between tests
  - staff_admin_client : authenticated admin HTTP client with a tenant + property
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

STAFF_ADMIN_EMAIL = "staff_admin@example.com"
STAFF_ADMIN_PASSWORD = "SecurePassword123!"


@pytest.fixture(scope="session")
def staff_token_store() -> dict:
    return {}


async def _register_and_login(client: AsyncClient, store: dict) -> None:
    payload = {
        "email": STAFF_ADMIN_EMAIL,
        "password": STAFF_ADMIN_PASSWORD,
        "full_name": "Staff Admin",
        "role": "admin",
        "phone": "9876543210",
    }
    resp = await client.post("/auth/users/register", json=payload)
    assert resp.status_code in (201, 409), f"Registration failed: {resp.text}"

    resp = await client.post(
        "/auth/users/verify-otp", json={"email": STAFF_ADMIN_EMAIL, "otp": "123456"}
    )
    assert resp.status_code in (200, 400), f"OTP verification failed: {resp.text}"

    login = {"username": STAFF_ADMIN_EMAIL, "password": STAFF_ADMIN_PASSWORD}
    resp = await client.post("/auth/login", data=login)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    store["access_token"] = resp.json()["access_token"]


async def _create_tenant_and_property(client: AsyncClient, store: dict) -> None:
    headers = {"Authorization": f"Bearer {store['access_token']}"}

    if "tenant_id" not in store:
        resp = await client.post(
            "/tenants/",
            json={"name": "Staff Test Hotel", "currency": "USD", "timezone": "UTC"},
            headers=headers,
        )
        assert resp.status_code in (201, 409), f"Tenant creation failed: {resp.text}"
        store["tenant_id"] = resp.json()["data"]["id"]

    property_payload = {
        "name": "Staff Test Property",
        "type": "HOTEL",
        "description": "Hotel for staff tests",
        "phone_number": "1234567890",
        "email": "staff@property.com",
        "total_rooms": 10,
        "number_of_floors": 3,
    }
    resp = await client.post(
        "/properties/general-information",
        json=property_payload,
        headers=headers,
    )
    assert resp.status_code == 201, f"Property creation failed: {resp.text}"
    store["property_id"] = resp.json()["data"]["id"]


@pytest_asyncio.fixture(scope="function")
async def staff_admin_client(
    async_client: AsyncClient, staff_token_store: dict
) -> AsyncClient:
    """HTTP client pre-authenticated as a tenant admin with a property."""
    if "access_token" not in staff_token_store:
        await _register_and_login(async_client, staff_token_store)
        await _create_tenant_and_property(async_client, staff_token_store)
    yield async_client


@pytest_asyncio.fixture(scope="function")
async def staff_property_id(staff_admin_client: AsyncClient, staff_token_store: dict) -> str:
    return staff_token_store["property_id"]