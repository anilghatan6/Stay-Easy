"""
Tests for /auth/guests/* endpoints.

Tests run in declaration order and share state through `token_store`:
  register → invalid OTP → resend OTP → verify OTP → login → /me → refresh
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_guest(async_client: AsyncClient):
    payload = {
        "email": "guest@example.com",
        "password": "SecurePassword123!",
        "full_name": "John Doe",
        "phone": "1234567890",
        "nationality": "US",
    }
    response = await async_client.post("/auth/guests/register", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert "guest_id" in data
    assert data["email"] == "guest@example.com"
    assert data["message"] == "Guest registered successfully. Please verify your email."


@pytest.mark.asyncio
async def test_verify_invalid_otp(async_client: AsyncClient):
    """Supplying a wrong OTP must be rejected (400/401)."""
    payload = {"email": "guest@example.com", "otp": "000000"}
    response = await async_client.post("/auth/guests/verify-otp", json=payload)
    assert response.status_code in (400, 401), response.text


@pytest.mark.asyncio
async def test_resend_otp(async_client: AsyncClient):
    payload = {"email": "guest@example.com"}
    response = await async_client.post("/auth/guests/resend-otp", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Verification code resent successfully."


@pytest.mark.asyncio
async def test_verify_otp(async_client: AsyncClient, token_store: dict):
    payload = {"email": "guest@example.com", "otp": "123456"}
    response = await async_client.post("/auth/guests/verify-otp", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_login_guest(async_client: AsyncClient, token_store: dict):
    # OAuth2PasswordRequestForm uses form encoding
    data = {"username": "guest@example.com", "password": "SecurePassword123!"}
    response = await async_client.post("/auth/guests/login", data=data)
    assert response.status_code == 200, response.text
    json_resp = response.json()
    assert "access_token" in json_resp
    assert "refresh_token" in json_resp
    token_store["guest_access"] = json_resp["access_token"]
    token_store["guest_refresh"] = json_resp["refresh_token"]


@pytest.mark.asyncio
async def test_get_current_guest(async_client: AsyncClient, token_store: dict):
    headers = {"Authorization": f"Bearer {token_store['guest_access']}"}
    response = await async_client.get("/auth/guests/me", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["email"] == "guest@example.com"
    assert data["full_name"] == "John Doe"
   


@pytest.mark.asyncio
async def test_refresh_token(async_client: AsyncClient, token_store: dict):
    payload = {"refresh_token": token_store["guest_refresh"]}
    response = await async_client.post("/auth/guests/refresh", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
