"""
Tests for /auth/users/* endpoints.

Tests run in declaration order and share state through `token_store`:
  register → invalid OTP → resend OTP → verify OTP → login → /me → refresh
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(async_client: AsyncClient):
    payload = {
        "email": "admin@example.com",
        "password": "SecurePassword123!",
        "full_name":"John Doe",
        "role": "admin",
        "phone": "1234567890",
    }
    response = await async_client.post("/auth/users/register", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert "user_id" in data
    assert data["email"] == "admin@example.com"
    assert data["message"] == "User registered successfully. Please verify your email."


@pytest.mark.asyncio
async def test_verify_invalid_otp(async_client: AsyncClient):
    """Supplying a wrong OTP must be rejected (400/401)."""
    payload = {"email": "admin@example.com", "otp": "000000"}
    response = await async_client.post("/auth/users/verify-otp", json=payload)
    assert response.status_code in (400, 401), response.text


@pytest.mark.asyncio
async def test_resend_otp(async_client: AsyncClient):
    payload = {"email": "admin@example.com"}
    response = await async_client.post("/auth/users/resend-otp", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Verification code resent successfully."


@pytest.mark.asyncio
async def test_verify_otp(async_client: AsyncClient, token_store: dict):
    payload = {"email": "admin@example.com", "otp": "123456"}
    response = await async_client.post("/auth/users/verify-otp", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_login_user(async_client: AsyncClient, token_store: dict):
    data = {"username": "admin@example.com", "password": "SecurePassword123!"}
    response = await async_client.post("/auth/users/login", data=data)
    assert response.status_code == 200, response.text
    json_resp = response.json()
    assert "access_token" in json_resp
    assert "refresh_token" in json_resp
    token_store["user_access"] = json_resp["access_token"]
    token_store["user_refresh"] = json_resp["refresh_token"]


@pytest.mark.asyncio
async def test_get_current_user(async_client: AsyncClient, token_store: dict):
    headers = {"Authorization": f"Bearer {token_store['user_access']}"}
    response = await async_client.get("/auth/users/me", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["email"] == "admin@example.com"
    assert data["full_name"] == "John Doe"


@pytest.mark.asyncio
async def test_refresh_token(async_client: AsyncClient, token_store: dict):
    payload = {"refresh_token": token_store["user_refresh"]}
    response = await async_client.post("/auth/users/refresh", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
