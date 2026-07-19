"""
Tests for /tenants/* endpoints.

Execution order (pytest-ordering by declaration):
  create_tenant_no_auth → create_tenant → get_tenant → update_tenant → delete_tenant
"""
import pytest
from httpx import AsyncClient


# ─── helpers ────────────────────────────────────────────────────────────────

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ────────────────────────────────────────────────────────────────────────────
# Setup: register & verify a fresh user for tenant tests
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tenant_store() -> dict:
    return {}


@pytest.mark.asyncio
async def test_register_and_login_for_tenant_tests(
    async_client: AsyncClient, tenant_store: dict
):
    """Bootstrap: register → verify OTP → capture token."""
    # Register
    resp = await async_client.post(
        "/auth/users/register",
        json={
            "email": "tenant_admin@example.com",
            "password": "SecurePassword123!",
            "full_name": "Tenant Admin",
            "role": "admin",
            "phone": "1111111111",
        },
    )
    assert resp.status_code == 201, resp.text

    # Verify OTP (pinned to 123456 by mock)
    resp = await async_client.post(
        "/auth/users/verify-otp",
        json={"email": "tenant_admin@example.com", "otp": "123456"},
    )
    assert resp.status_code == 200, resp.text

    # Login to retrieve token
    resp = await async_client.post(
        "/auth/users/login",
        data={"username": "tenant_admin@example.com", "password": "SecurePassword123!"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    tenant_store["access_token"] = data["access_token"]


# ────────────────────────────────────────────────────────────────────────────
# GET /tenants/ — no tenant yet → 404 / 400
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_tenant_when_none_exists(
    async_client: AsyncClient, tenant_store: dict
):
    """Fetching tenant before creation should return 400 or 404."""
    resp = await async_client.get(
        "/tenants/", headers=auth_headers(tenant_store["access_token"])
    )
    assert resp.status_code in (400, 404), resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /tenants/ — unauthenticated → 401/403
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_tenant_unauthenticated(async_client: AsyncClient):
    """Creating a tenant without a token should be refused."""
    resp = await async_client.post(
        "/tenants/",
        json={"name": "Ghost Hotel", "currency": "USD", "timezone": "UTC"},
    )
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /tenants/ — success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_tenant(async_client: AsyncClient, tenant_store: dict):
    resp = await async_client.post(
        "/tenants/",
        json={
            "name": "Grand Hotel",
            "currency": "USD",
            "timezone": "Asia/Kathmandu",
        },
        headers=auth_headers(tenant_store["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    tenant = data["data"]
    assert tenant["name"] == "Grand Hotel"
    assert tenant["currency"] == "USD"
    assert tenant["timezone"] == "Asia/Kathmandu"
    assert "id" in tenant
    tenant_store["tenant_id"] = tenant["id"]


# ────────────────────────────────────────────────────────────────────────────
# POST /tenants/ — duplicate → 400 / 409
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_duplicate_tenant(async_client: AsyncClient, tenant_store: dict):
    """Creating a second tenant with the same name should fail."""
    resp = await async_client.post(
        "/tenants/",
        json={"name": "Grand Hotel", "currency": "USD", "timezone": "UTC"},
        headers=auth_headers(tenant_store["access_token"]),
    )
    assert resp.status_code in (400, 409, 422), resp.text


# ────────────────────────────────────────────────────────────────────────────
# GET /tenants/ — success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_tenant(async_client: AsyncClient, tenant_store: dict):
    resp = await async_client.get(
        "/tenants/", headers=auth_headers(tenant_store["access_token"])
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["id"] == tenant_store["tenant_id"]
    assert data["data"]["name"] == "Grand Hotel"


# ────────────────────────────────────────────────────────────────────────────
# PATCH /tenants/ — success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_tenant(async_client: AsyncClient, tenant_store: dict):
    resp = await async_client.patch(
        "/tenants/",
        json={"name": "Grand Hotel Updated", "currency": "NZD"},
        headers=auth_headers(tenant_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    updated = data["data"]
    assert updated["name"] == "Grand Hotel Updated"
    assert updated["currency"] == "NZD"


# ────────────────────────────────────────────────────────────────────────────
# PATCH /tenants/ — invalid timezone → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_tenant_invalid_timezone(
    async_client: AsyncClient, tenant_store: dict
):
    resp = await async_client.patch(
        "/tenants/",
        json={"timezone": "Mars/Olympus"},
        headers=auth_headers(tenant_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# DELETE /tenants/
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_tenant(async_client: AsyncClient, tenant_store: dict):
    resp = await async_client.delete(
        "/tenants/", headers=auth_headers(tenant_store["access_token"])
    )
    # 204 No Content on success
    assert resp.status_code == 204, resp.text
