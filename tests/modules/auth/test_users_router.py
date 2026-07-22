"""
Tests for /auth/users/* endpoints.
"""
import pytest
from httpx import AsyncClient


VALID_PAYLOAD = {
    "email": "admin@example.com",
    "password": "SecurePassword123!",
    "full_name": "John Doe",
    "role": "admin",
    "phone": "1234567890",
}


# ── POST /auth/users/register ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_user_success(async_client: AsyncClient):
    resp = await async_client.post("/auth/users/register", json=VALID_PAYLOAD)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["email"] == VALID_PAYLOAD["email"]
    assert data["message"] == "User registered successfully. Please verify your email."


@pytest.mark.asyncio
async def test_register_user_empty_body(async_client: AsyncClient):
    resp = await async_client.post("/auth/users/register", json={})
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_register_user_invalid_email(async_client: AsyncClient):
    payload = {**VALID_PAYLOAD, "email": "not-an-email"}
    resp = await async_client.post("/auth/users/register", json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_register_user_short_password(async_client: AsyncClient):
    payload = {**VALID_PAYLOAD, "password": "Ab1!"}
    resp = await async_client.post("/auth/users/register", json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_register_user_weak_password_no_digit(async_client: AsyncClient):
    payload = {**VALID_PAYLOAD, "password": "SecurePassword!"}
    resp = await async_client.post("/auth/users/register", json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_register_user_weak_password_no_special(async_client: AsyncClient):
    payload = {**VALID_PAYLOAD, "password": "SecurePassword1"}
    resp = await async_client.post("/auth/users/register", json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_register_user_short_name(async_client: AsyncClient):
    payload = {**VALID_PAYLOAD, "full_name": "A"}
    resp = await async_client.post("/auth/users/register", json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_register_user_name_invalid_chars(async_client: AsyncClient):
    payload = {**VALID_PAYLOAD, "full_name": "John123"}
    resp = await async_client.post("/auth/users/register", json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_register_user_missing_phone(async_client: AsyncClient):
    payload = {
        "email": "admin-nophone@example.com",
        "password": "SecurePassword123!",
        "full_name": "Jane Doe",
    }
    resp = await async_client.post("/auth/users/register", json=payload)
    assert resp.status_code == 201, resp.text


# ── POST /auth/users/verify-otp ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_invalid_otp(async_client: AsyncClient):
    payload = {"email": "admin@example.com", "otp": "000000"}
    resp = await async_client.post("/auth/users/verify-otp", json=payload)
    assert resp.status_code in (400, 401), resp.text


# ── POST /auth/users/resend-otp ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resend_otp(async_client: AsyncClient):
    payload = {"email": "admin@example.com"}
    resp = await async_client.post("/auth/users/resend-otp", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["message"] == "Verification code resent successfully."


# ── POST /auth/users/verify-otp (valid) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_otp(async_client: AsyncClient, token_store: dict):
    payload = {"email": "admin@example.com", "otp": "123456"}
    resp = await async_client.post("/auth/users/verify-otp", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"


# ── POST /auth/users/login ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_user_success(async_client: AsyncClient, token_store: dict):
    resp = await async_client.post(
        "/auth/users/login",
        data={"username": "admin@example.com", "password": "SecurePassword123!"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    token_store["user_access"] = data["access_token"]
    token_store["user_refresh"] = data["refresh_token"]


@pytest.mark.asyncio
async def test_login_user_wrong_password(async_client: AsyncClient):
    resp = await async_client.post(
        "/auth/users/login",
        data={"username": "admin@example.com", "password": "WrongPassword1!"},
    )
    assert resp.status_code == 400, resp.text


# ── GET /auth/users/me ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_current_user_unauthorized(async_client: AsyncClient):
    resp = await async_client.get("/auth/users/me")
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(async_client: AsyncClient):
    resp = await async_client.get(
        "/auth/users/me", headers={"Authorization": "Bearer invalid"}
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_current_user_success(async_client: AsyncClient, token_store: dict):
    headers = {"Authorization": f"Bearer {token_store['user_access']}"}
    resp = await async_client.get("/auth/users/me", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email"] == "admin@example.com"
    assert data["full_name"] == "John Doe"
    assert "role" in data


# ── POST /auth/users/refresh ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_token(async_client: AsyncClient, token_store: dict):
    payload = {"refresh_token": token_store["user_refresh"]}
    resp = await async_client.post("/auth/users/refresh", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_refresh_invalid_token(async_client: AsyncClient):
    payload = {"refresh_token": "invalid-token"}
    resp = await async_client.post("/auth/users/refresh", json=payload)
    assert resp.status_code == 401, resp.text
