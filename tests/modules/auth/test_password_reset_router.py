"""
Endpoint tests for the password-reset flow.

Covers:
- POST /auth/forgot-password
- POST /auth/reset-password
- POST /auth/guest/change-password
- POST /auth/user/change-password
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.modules.auth.models.guests_model import Guest
from app.modules.auth.models.password_reset_token_model import PasswordResetToken
from app.modules.auth.models.users_model import User
from app.modules.auth.services.password_reset_services import hash_reset_token
from app.utils.exceptions import EmailDeliveryError

from tests.modules.auth.conftest import (
    DEFAULT_PASSWORD,
    RESET_GUEST_EMAIL,
    RESET_USER_EMAIL,
    create_verified_guest,
    create_verified_user,
)

FORGOT_OK_MESSAGE = "you will receive password reset instructions"
RESET_OK_MESSAGE = "Password reset successfully"
CHANGE_OK_MESSAGE = "Password changed successfully"
NEW_PASSWORD = "NewSecurePass456!"


# ── DB helpers ───────────────────────────────────────────────────────────────

async def _get_user_by_email(db_session, email: str) -> User | None:
    result = await db_session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _get_guest_by_email(db_session, email: str) -> Guest | None:
    result = await db_session.execute(select(Guest).where(Guest.email == email))
    return result.scalar_one_or_none()


async def _count_tokens_for(db_session, user_id=None, guest_id=None) -> int:
    stmt = select(func.count()).select_from(PasswordResetToken)
    if user_id is not None:
        stmt = stmt.where(PasswordResetToken.user_id == user_id)
    if guest_id is not None:
        stmt = stmt.where(PasswordResetToken.guest_id == guest_id)
    result = await db_session.execute(stmt)
    return result.scalar_one()


async def _insert_token(
    db_session,
    raw_token: str,
    expires_at: datetime,
    user_id=None,
    guest_id=None,
    used_at: datetime | None = None,
) -> PasswordResetToken:
    row = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user_id,
        guest_id=guest_id,
        token_hash=hash_reset_token(raw_token),
        expires_at=expires_at,
        used_at=used_at,
    )
    db_session.add(row)
    await db_session.commit()
    return row


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════
# POST /auth/forgot-password
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_forgot_password_existing_user(
    pr_user_client: AsyncClient, pr_email_capture, db_session
):
    resp = await pr_user_client.post(
        "/auth/forgot-password", json={"email": RESET_USER_EMAIL}
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["success"] is True
    assert FORGOT_OK_MESSAGE in body["data"]

    pr_email_capture.assert_awaited_once()
    call = pr_email_capture.await_args
    assert call.kwargs["to_email"] == RESET_USER_EMAIL

    user = await _get_user_by_email(db_session, RESET_USER_EMAIL)
    assert user is not None
    assert await _count_tokens_for(db_session, user_id=user.id) == 1

    raw_token = call.kwargs["token"]
    result = await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    token_row = result.scalar_one()
    assert token_row.token_hash == hash_reset_token(raw_token)
    assert token_row.guest_id is None
    assert token_row.used_at is None
    assert token_row.expires_at > datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)


@pytest.mark.asyncio
async def test_forgot_password_existing_guest(
    pr_guest_client: AsyncClient, pr_email_capture, db_session
):
    resp = await pr_guest_client.post(
        "/auth/forgot-password", json={"email": RESET_GUEST_EMAIL}
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["success"] is True

    pr_email_capture.assert_awaited_once()
    call = pr_email_capture.await_args
    assert call.kwargs["to_email"] == RESET_GUEST_EMAIL

    guest = await _get_guest_by_email(db_session, RESET_GUEST_EMAIL)
    assert guest is not None
    assert await _count_tokens_for(db_session, guest_id=guest.id) == 1

    result = await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.guest_id == guest.id)
    )
    token_row = result.scalar_one()
    assert token_row.token_hash == hash_reset_token(call.kwargs["token"])
    assert token_row.user_id is None


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_no_account_leak(
    pr_user_client: AsyncClient, pr_email_capture
):
    resp = await pr_user_client.post(
        "/auth/forgot-password", json={"email": "nobody@nowhere.com"}
    )
    assert resp.status_code == 202, resp.text
    assert FORGOT_OK_MESSAGE in resp.json()["data"]
    pr_email_capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_forgot_password_case_insensitive_email(
    pr_user_client: AsyncClient, pr_email_capture, db_session
):
    resp = await pr_user_client.post(
        "/auth/forgot-password", json={"email": RESET_USER_EMAIL.upper()}
    )
    assert resp.status_code == 202, resp.text
    pr_email_capture.assert_awaited_once()
    assert pr_email_capture.await_args.kwargs["to_email"] == RESET_USER_EMAIL

    user = await _get_user_by_email(db_session, RESET_USER_EMAIL)
    assert await _count_tokens_for(db_session, user_id=user.id) == 1


@pytest.mark.asyncio
async def test_forgot_password_replaces_previous_token(
    pr_user_client: AsyncClient, pr_email_capture, db_session
):
    for _ in range(2):
        resp = await pr_user_client.post(
            "/auth/forgot-password", json={"email": RESET_USER_EMAIL}
        )
        assert resp.status_code == 202, resp.text

    assert pr_email_capture.await_count == 2
    user = await _get_user_by_email(db_session, RESET_USER_EMAIL)
    assert await _count_tokens_for(db_session, user_id=user.id) == 1


@pytest.mark.asyncio
async def test_forgot_password_email_delivery_failure_still_202(
    pr_user_client: AsyncClient, pr_email_capture, db_session
):
    pr_email_capture.side_effect = EmailDeliveryError("SMTP down")

    resp = await pr_user_client.post(
        "/auth/forgot-password", json={"email": RESET_USER_EMAIL}
    )
    assert resp.status_code == 202, resp.text

    user = await _get_user_by_email(db_session, RESET_USER_EMAIL)
    assert await _count_tokens_for(db_session, user_id=user.id) == 1


@pytest.mark.asyncio
async def test_forgot_password_invalid_email(pr_user_client: AsyncClient):
    resp = await pr_user_client.post(
        "/auth/forgot-password", json={"email": "not-an-email"}
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_forgot_password_missing_email(pr_user_client: AsyncClient):
    resp = await pr_user_client.post("/auth/forgot-password", json={})
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_forgot_password_email_too_long(pr_user_client: AsyncClient):
    long_email = f"{'a' * 115}@example.com"
    assert len(long_email) > 120
    resp = await pr_user_client.post(
        "/auth/forgot-password", json={"email": long_email}
    )
    assert resp.status_code == 422, resp.text


# ═══════════════════════════════════════════════════════════════════════════
# POST /auth/reset-password
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_reset_password_user_success(
    pr_user_client: AsyncClient, pr_email_capture, db_session
):
    email = f"flow.user{uuid.uuid4().hex[:8]}@example.com"
    await create_verified_user(pr_user_client, email)

    resp = await pr_user_client.post("/auth/forgot-password", json={"email": email})
    assert resp.status_code == 202, resp.text
    raw_token = pr_email_capture.await_args.kwargs["token"]

    resp = await pr_user_client.post(
        "/auth/reset-password", json={"token": raw_token, "new_password": NEW_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    assert RESET_OK_MESSAGE in resp.json()["data"]

    resp = await pr_user_client.post(
        "/auth/login", data={"username": email, "password": DEFAULT_PASSWORD}
    )
    assert resp.status_code == 400, resp.text
    resp = await pr_user_client.post(
        "/auth/login", data={"username": email, "password": NEW_PASSWORD}
    )
    assert resp.status_code == 200, resp.text

    user = await _get_user_by_email(db_session, email)
    assert await _count_tokens_for(db_session, user_id=user.id) == 0


@pytest.mark.asyncio
async def test_reset_password_guest_success(
    pr_guest_client: AsyncClient, pr_email_capture, db_session
):
    email = f"flow.guest{uuid.uuid4().hex[:8]}@example.com"
    await create_verified_guest(pr_guest_client, email)

    resp = await pr_guest_client.post("/auth/forgot-password", json={"email": email})
    assert resp.status_code == 202, resp.text
    raw_token = pr_email_capture.await_args.kwargs["token"]

    resp = await pr_guest_client.post(
        "/auth/reset-password", json={"token": raw_token, "new_password": NEW_PASSWORD}
    )
    assert resp.status_code == 200, resp.text

    resp = await pr_guest_client.post(
        "/auth/login", data={"username": email, "password": NEW_PASSWORD}
    )
    assert resp.status_code == 200, resp.text

    guest = await _get_guest_by_email(db_session, email)
    assert await _count_tokens_for(db_session, guest_id=guest.id) == 0


@pytest.mark.asyncio
async def test_reset_password_invalid_token(pr_user_client: AsyncClient):
    resp = await pr_user_client.post(
        "/auth/reset-password",
        json={"token": "no-such-token", "new_password": NEW_PASSWORD},
    )
    assert resp.status_code == 400, resp.text
    assert "expired" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_reset_password_empty_token(pr_user_client: AsyncClient):
    resp = await pr_user_client.post(
        "/auth/reset-password",
        json={"token": "", "new_password": NEW_PASSWORD},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_reset_password_expired_token_deleted(
    pr_user_client: AsyncClient, db_session
):
    email = f"expired.user{uuid.uuid4().hex[:8]}@example.com"
    await create_verified_user(pr_user_client, email)
    user = await _get_user_by_email(db_session, email)
    user_id = user.id
    raw_token = "expired-raw-token"
    await _insert_token(
        db_session,
        raw_token,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        user_id=user_id,
    )

    resp = await pr_user_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": NEW_PASSWORD},
    )
    assert resp.status_code == 400, resp.text
    assert "expired" in resp.json()["error"].lower()
    assert await _count_tokens_for(db_session, user_id=user_id) == 0


@pytest.mark.asyncio
async def test_reset_password_already_used_token_kept(
    pr_user_client: AsyncClient, db_session
):
    email = f"used.user{uuid.uuid4().hex[:8]}@example.com"
    await create_verified_user(pr_user_client, email)
    user = await _get_user_by_email(db_session, email)
    user_id = user.id
    raw_token = "used-raw-token"
    await _insert_token(
        db_session,
        raw_token,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        user_id=user_id,
        used_at=datetime.now(UTC),
    )

    resp = await pr_user_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": NEW_PASSWORD},
    )
    assert resp.status_code == 400, resp.text
    assert await _count_tokens_for(db_session, user_id=user_id) == 1


@pytest.mark.asyncio
async def test_reset_password_token_for_missing_user(pr_user_client: AsyncClient, db_session):
    raw_token = "orphan-user-token"
    await _insert_token(
        db_session,
        raw_token,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        user_id=uuid.uuid4(),
    )

    resp = await pr_user_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": NEW_PASSWORD},
    )
    assert resp.status_code == 400, resp.text
    assert "expired" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_reset_password_token_for_missing_guest(pr_user_client: AsyncClient, db_session):
    raw_token = "orphan-guest-token"
    await _insert_token(
        db_session,
        raw_token,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        guest_id=uuid.uuid4(),
    )

    resp = await pr_user_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": NEW_PASSWORD},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "weak_password",
    [
        "Short1!",                 # too short
        "NoSpecialChars1",         # no special character
        "NoDigitHere!",            # no digit
        "Has Space 1!",            # contains a space
    ],
)
async def test_reset_password_weak_new_password(
    pr_user_client: AsyncClient, weak_password: str
):
    resp = await pr_user_client.post(
        "/auth/reset-password",
        json={"token": "whatever", "new_password": weak_password},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_reset_password_missing_fields(pr_user_client: AsyncClient):
    resp = await pr_user_client.post(
        "/auth/reset-password", json={"token": "x"}
    )
    assert resp.status_code == 422, resp.text
    resp = await pr_user_client.post(
        "/auth/reset-password", json={"new_password": NEW_PASSWORD}
    )
    assert resp.status_code == 422, resp.text


# ═══════════════════════════════════════════════════════════════════════════
# POST /auth/guest/change-password
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_change_guest_password_success(async_client: AsyncClient):
    email = f"cp.guest{uuid.uuid4().hex[:8]}@example.com"
    token = await create_verified_guest(async_client, email)

    resp = await async_client.post(
        "/auth/guest/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
        headers=_auth_headers(token["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    assert CHANGE_OK_MESSAGE in resp.json()["data"]

    resp = await async_client.post(
        "/auth/login", data={"username": email, "password": DEFAULT_PASSWORD}
    )
    assert resp.status_code == 400, resp.text
    resp = await async_client.post(
        "/auth/login", data={"username": email, "password": NEW_PASSWORD}
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_change_guest_password_wrong_current(async_client: AsyncClient):
    email = f"cp.guest{uuid.uuid4().hex[:8]}@example.com"
    token = await create_verified_guest(async_client, email)

    resp = await async_client.post(
        "/auth/guest/change-password",
        json={"current_password": "WrongPassword1!", "new_password": NEW_PASSWORD},
        headers=_auth_headers(token["access_token"]),
    )
    assert resp.status_code == 400, resp.text
    assert "incorrect" in resp.json()["error"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "weak_password",
    [
        "Short1!",
        "NoSpecialChars1",
        "NoDigitHere!",
        "Has Space 1!",
    ],
)
async def test_change_guest_password_weak_new(
    async_client: AsyncClient, weak_password: str
):
    email = f"cp.guest{uuid.uuid4().hex[:8]}@example.com"
    token = await create_verified_guest(async_client, email)

    resp = await async_client.post(
        "/auth/guest/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": weak_password},
        headers=_auth_headers(token["access_token"]),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_change_guest_password_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/auth/guest/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_change_guest_password_with_invalid_token(async_client: AsyncClient):
    resp = await async_client.post(
        "/auth/guest/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
        headers=_auth_headers("not-a-real-jwt"),
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_change_guest_password_with_admin_token_rejected(
    async_client: AsyncClient, pr_user_client: AsyncClient, pr_token_store: dict
):
    resp = await async_client.post(
        "/auth/guest/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
        headers=_auth_headers(pr_token_store["pr_user_token"]),
    )
    assert resp.status_code == 403, resp.text


# ═══════════════════════════════════════════════════════════════════════════
# POST /auth/user/change-password
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_change_user_password_success(async_client: AsyncClient):
    email = f"cp.user{uuid.uuid4().hex[:8]}@example.com"
    token = await create_verified_user(async_client, email)

    resp = await async_client.post(
        "/auth/user/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
        headers=_auth_headers(token["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    assert CHANGE_OK_MESSAGE in resp.json()["data"]

    resp = await async_client.post(
        "/auth/login", data={"username": email, "password": DEFAULT_PASSWORD}
    )
    assert resp.status_code == 400, resp.text
    resp = await async_client.post(
        "/auth/login", data={"username": email, "password": NEW_PASSWORD}
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_change_user_password_wrong_current(async_client: AsyncClient):
    email = f"cp.user{uuid.uuid4().hex[:8]}@example.com"
    token = await create_verified_user(async_client, email)

    resp = await async_client.post(
        "/auth/user/change-password",
        json={"current_password": "WrongPassword1!", "new_password": NEW_PASSWORD},
        headers=_auth_headers(token["access_token"]),
    )
    assert resp.status_code == 400, resp.text
    assert "incorrect" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_change_user_password_weak_new(async_client: AsyncClient):
    email = f"cp.user{uuid.uuid4().hex[:8]}@example.com"
    token = await create_verified_user(async_client, email)

    resp = await async_client.post(
        "/auth/user/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "Short1!"},
        headers=_auth_headers(token["access_token"]),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_change_user_password_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/auth/user/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_change_user_password_with_guest_token_rejected(
    async_client: AsyncClient, pr_guest_client: AsyncClient, pr_token_store: dict
):
    resp = await async_client.post(
        "/auth/user/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
        headers=_auth_headers(pr_token_store["pr_guest_token"]),
    )
    assert resp.status_code == 403, resp.text
