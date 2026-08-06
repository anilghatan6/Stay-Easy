"""
Shared fixtures for the auth module's password-reset tests.
"""
import pytest
import pytest_asyncio

RESET_USER_EMAIL = "reset.user@example.com"
RESET_GUEST_EMAIL = "reset.guest@example.com"
DEFAULT_PASSWORD = "SecurePassword123!"


@pytest.fixture(scope="session")
def pr_token_store() -> dict:
    """Holds access tokens produced by the shared (once-only) registrations."""
    return {}


async def create_verified_user(
    client, email: str, password: str = DEFAULT_PASSWORD, full_name: str = "Reset User"
) -> dict:
    """Registers, verifies OTP and logs in a user; returns the token dict."""
    resp = await client.post(
        "/auth/users/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        "/auth/users/verify-otp", json={"email": email, "otp": "123456"}
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"access_token": resp.json()["access_token"]}


async def create_verified_guest(
    client, email: str, password: str = DEFAULT_PASSWORD, full_name: str = "Reset Guest"
) -> dict:
    """Registers, verifies OTP and logs in a guest; returns the token dict."""
    resp = await client.post(
        "/auth/guests/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "phone": "9876543210",
        },
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        "/auth/guests/verify-otp", json={"email": email, "otp": "123456"}
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"access_token": resp.json()["access_token"]}


@pytest_asyncio.fixture(scope="function")
async def pr_user_client(async_client, pr_token_store):
    """Client with a shared verified admin user (registered once per session)."""
    if "pr_user_token" not in pr_token_store:
        token = await create_verified_user(async_client, RESET_USER_EMAIL)
        pr_token_store["pr_user_token"] = token["access_token"]
    return async_client


@pytest_asyncio.fixture(scope="function")
async def pr_guest_client(async_client, pr_token_store):
    """Client with a shared verified guest (registered once per session)."""
    if "pr_guest_token" not in pr_token_store:
        token = await create_verified_guest(async_client, RESET_GUEST_EMAIL)
        pr_token_store["pr_guest_token"] = token["access_token"]
    return async_client


@pytest.fixture
def pr_email_capture(mocker):
    """Mocks send_password_reset_email so the raw reset token can be inspected."""
    from app.utils.mail_services import password_reset_services as prs

    mock = mocker.patch.object(prs, "send_password_reset_email", new_callable=mocker.AsyncMock)
    return mock
