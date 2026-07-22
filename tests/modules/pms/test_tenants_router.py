"""
Tests for /tenants/* endpoints.

Execution order relies on declaration order + shared tenant_store:
  auth-less tests → register → pre-creation tests → CRUD → post-deletion tests
"""
import pytest
from httpx import AsyncClient


# ─── helpers ────────────────────────────────────────────────────────────────

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ────────────────────────────────────────────────────────────────────────────
# Shared mutable state (session-scoped)
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def tenant_store() -> dict:
    return {}


# ────────────────────────────────────────────────────────────────────────────
# Unauthenticated tests (no token needed, run before any auth setup)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_tenant_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/tenants/",
        json={"name": "Ghost Hotel", "currency": "USD", "timezone": "UTC"},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_tenant_unauthenticated(async_client: AsyncClient):
    resp = await async_client.get("/tenants/")
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_update_tenant_unauthenticated(async_client: AsyncClient):
    resp = await async_client.patch("/tenants/", json={"name": "Hacked Hotel"})
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_delete_tenant_unauthenticated(async_client: AsyncClient):
    resp = await async_client.delete("/tenants/")
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# Bootstrap: register & verify a fresh user for tenant tests
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_and_login_for_tenant_tests(
    async_client: AsyncClient, tenant_store: dict
):
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

    resp = await async_client.post(
        "/auth/users/verify-otp",
        json={"email": "tenant_admin@example.com", "otp": "123456"},
    )
    assert resp.status_code == 200, resp.text

    resp = await async_client.post(
        "/auth/users/login",
        data={"username": "tenant_admin@example.com", "password": "SecurePassword123!"},
    )
    assert resp.status_code == 200, resp.text
    tenant_store["access_token"] = resp.json()["access_token"]


# ────────────────────────────────────────────────────────────────────────────
# GET /tenants/ — no tenant yet → 400 / 404
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_tenant_when_none_exists(
    async_client: AsyncClient, tenant_store: dict
):
    resp = await async_client.get(
        "/tenants/", headers=auth_headers(tenant_store["access_token"])
    )
    assert resp.status_code in (400, 404), resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /tenants/ — validation failures → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_tenant_empty_body(
    async_client: AsyncClient, tenant_store: dict
):
    resp = await async_client.post(
        "/tenants/",
        json={},
        headers=auth_headers(tenant_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_tenant_name_too_short(
    async_client: AsyncClient, tenant_store: dict
):
    resp = await async_client.post(
        "/tenants/",
        json={"name": "A"},
        headers=auth_headers(tenant_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_tenant_name_exceeds_max_length(
    async_client: AsyncClient, tenant_store: dict
):
    resp = await async_client.post(
        "/tenants/",
        json={"name": "A" * 256},
        headers=auth_headers(tenant_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


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
    assert "id" in tenant
    assert "owner_id" in tenant
    assert "created_at" in tenant
    tenant_store["tenant_id"] = tenant["id"]


# ────────────────────────────────────────────────────────────────────────────
# POST /tenants/ — duplicate → 400 / 409
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_duplicate_tenant(
    async_client: AsyncClient, tenant_store: dict
):
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


# ────────────────────────────────────────────────────────────────────────────
# PATCH /tenants/ — name too short → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_tenant_name_too_short(
    async_client: AsyncClient, tenant_store: dict
):
    resp = await async_client.patch(
        "/tenants/",
        json={"name": "X"},
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
    assert resp.status_code == 204, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Lifecycle tests — operations after deletion → 400 / 404
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_tenant_after_deletion(
    async_client: AsyncClient, tenant_store: dict
):
    resp = await async_client.get(
        "/tenants/", headers=auth_headers(tenant_store["access_token"])
    )
    assert resp.status_code in (400, 404), resp.text


@pytest.mark.asyncio
async def test_update_tenant_after_deletion(
    async_client: AsyncClient, tenant_store: dict
):
    resp = await async_client.patch(
        "/tenants/",
        json={"name": "Ghost Hotel"},
        headers=auth_headers(tenant_store["access_token"]),
    )
    assert resp.status_code in (400, 404), resp.text
