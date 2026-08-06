"""
Unit tests for PasswordResetService business logic with mocked repositories.

These cover the failure paths that are unreachable through the HTTP layer
(RepositoryException / unexpected exceptions, anti-enumeration no-op, etc.)
as well as the token-hashing helpers.
"""
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.modules.auth.services.password_reset_services import (
    PasswordResetService,
    generate_reset_token,
    hash_reset_token,
)
from app.utils.exceptions import (
    EmailDeliveryError,
    InvalidAccountTypeException,
    InvalidPasswordException,
    InvalidResetTokenException,
    RepositoryException,
    ServiceException,
)


class FakeDB:
    def __init__(self):
        self.commit_calls = 0
        self.rollback_calls = 0

    async def commit(self):
        self.commit_calls += 1

    async def rollback(self):
        self.rollback_calls += 1


def make_token(
    *,
    raw: str = "raw-token",
    expires_at: datetime | None = None,
    used_at: datetime | None = None,
    user_id=None,
    guest_id=None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        token_hash=hash_reset_token(raw),
        expires_at=expires_at or (datetime.now(UTC) + timedelta(minutes=15)),
        used_at=used_at,
        user_id=user_id,
        guest_id=guest_id,
    )


def make_account(email: str = "person@example.com", kind: str = "user") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        email=email,
        full_name="Test Person",
        hashed_password="hashed-old",
        kind=kind,
    )


def build_service(
    mocker,
    db: FakeDB | None = None,
    password_reset_repo=None,
    user_repo=None,
    guest_repo=None,
    auth_service=None,
) -> PasswordResetService:
    return PasswordResetService(
        db=db or FakeDB(),
        password_reset_repo=(
            password_reset_repo if password_reset_repo is not None else mocker.AsyncMock()
        ),
        user_repo=user_repo if user_repo is not None else mocker.AsyncMock(),
        guest_repo=guest_repo if guest_repo is not None else mocker.AsyncMock(),
        auth_service=auth_service if auth_service is not None else mocker.MagicMock(),
    )


def patch_email(mocker):
    return mocker.patch(
        "app.utils.mail_services.send_password_reset_email",
        new_callable=mocker.AsyncMock,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def test_generate_reset_token_is_unique():
    assert generate_reset_token() != generate_reset_token()


def test_hash_reset_token_is_sha256_hex():
    digest = hash_reset_token("anything")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_hash_reset_token_is_deterministic():
    assert hash_reset_token("x") == hash_reset_token("x")
    assert hash_reset_token("x") != hash_reset_token("y")


# ═══════════════════════════════════════════════════════════════════════════
# request_password_reset
# ═══════════════════════════════════════════════════════════════════════════

async def test_request_password_reset_user_path(mocker):
    user = make_account()
    repo = mocker.AsyncMock()
    repo.find_user_by_email.return_value = user
    repo.find_guest_by_email.return_value = None
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)
    email_mock = patch_email(mocker)

    await svc.request_password_reset(user.email)

    repo.find_guest_by_email.assert_not_awaited()
    repo.delete_existing_tokens.assert_awaited_once_with(user_id=user.id)
    create_call = repo.create_token.await_args.kwargs
    assert create_call["user_id"] == user.id
    assert create_call.get("guest_id") is None
    assert create_call["token_hash"] == hash_reset_token(email_mock.await_args.kwargs["token"])
    assert db.commit_calls == 1
    email_mock.assert_awaited_once_with(
        to_email=user.email, username=user.full_name, token=email_mock.await_args.kwargs["token"]
    )


async def test_request_password_reset_guest_path(mocker):
    guest = make_account(kind="guest")
    repo = mocker.AsyncMock()
    repo.find_user_by_email.return_value = None
    repo.find_guest_by_email.return_value = guest
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)
    email_mock = patch_email(mocker)

    await svc.request_password_reset(guest.email)

    repo.delete_existing_tokens.assert_awaited_once_with(guest_id=guest.id)
    create_call = repo.create_token.await_args.kwargs
    assert create_call["guest_id"] == guest.id
    assert create_call.get("user_id") is None
    assert db.commit_calls == 1
    email_mock.assert_awaited_once_with(
        to_email=guest.email, username=guest.full_name, token=email_mock.await_args.kwargs["token"]
    )


async def test_request_password_reset_no_account_is_silent(mocker):
    repo = mocker.AsyncMock()
    repo.find_user_by_email.return_value = None
    repo.find_guest_by_email.return_value = None
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)
    email_mock = patch_email(mocker)

    await svc.request_password_reset("nobody@nowhere.com")

    repo.delete_existing_tokens.assert_not_awaited()
    repo.create_token.assert_not_awaited()
    email_mock.assert_not_awaited()
    assert db.commit_calls == 0
    assert db.rollback_calls == 0


async def test_request_password_reset_repository_error_re_raises(mocker):
    repo = mocker.AsyncMock()
    repo.find_user_by_email.side_effect = RepositoryException("boom")
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)

    with pytest.raises(RepositoryException):
        await svc.request_password_reset("x@y.com")

    assert db.rollback_calls == 1
    assert db.commit_calls == 0


async def test_request_password_reset_unexpected_error_becomes_service_exception(mocker):
    repo = mocker.AsyncMock()
    repo.find_user_by_email.side_effect = ValueError("boom")
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)

    with pytest.raises(ServiceException):
        await svc.request_password_reset("x@y.com")

    assert db.rollback_calls == 1


async def test_request_password_reset_email_failure_is_swallowed(mocker):
    user = make_account()
    repo = mocker.AsyncMock()
    repo.find_user_by_email.return_value = user
    repo.find_guest_by_email.return_value = None
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)
    email_mock = patch_email(mocker)
    email_mock.side_effect = EmailDeliveryError("SMTP down")

    await svc.request_password_reset(user.email)  # must not raise

    assert db.commit_calls == 1
    assert db.rollback_calls == 0
    repo.create_token.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════
# reset_password
# ═══════════════════════════════════════════════════════════════════════════

async def test_reset_password_unknown_token(mocker):
    repo = mocker.AsyncMock()
    repo.get_token_by_hash.return_value = None
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)

    with pytest.raises(InvalidResetTokenException):
        await svc.reset_password("bad-token", "NewSecurePass456!")

    assert db.rollback_calls == 1


async def test_reset_password_expired_token_is_deleted(mocker):
    user = make_account()
    token = make_token(
        expires_at=datetime.now(UTC) - timedelta(minutes=1), user_id=user.id
    )
    repo = mocker.AsyncMock()
    repo.get_token_by_hash.return_value = token
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)

    with pytest.raises(InvalidResetTokenException):
        await svc.reset_password("raw-token", "NewSecurePass456!")

    repo.delete_token.assert_awaited_once_with(token)
    assert db.commit_calls == 1
    assert db.rollback_calls == 1


async def test_reset_password_used_token_not_deleted(mocker):
    user = make_account()
    token = make_token(used_at=datetime.now(UTC), user_id=user.id)
    repo = mocker.AsyncMock()
    repo.get_token_by_hash.return_value = token
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)

    with pytest.raises(InvalidResetTokenException):
        await svc.reset_password("raw-token", "NewSecurePass456!")

    repo.delete_token.assert_not_awaited()
    assert db.rollback_calls == 1


async def test_reset_password_user_happy_path(mocker):
    user = make_account()
    token = make_token(user_id=user.id)
    repo = mocker.AsyncMock()
    repo.get_token_by_hash.return_value = token
    user_repo = mocker.AsyncMock()
    user_repo.get_user_by_id.return_value = user
    auth_service = mocker.MagicMock()
    auth_service.get_password_hash.return_value = "hashed-new"
    db = FakeDB()
    svc = build_service(
        mocker,
        db=db,
        password_reset_repo=repo,
        user_repo=user_repo,
        auth_service=auth_service,
    )

    await svc.reset_password("raw-token", "NewSecurePass456!")

    auth_service.get_password_hash.assert_called_once_with("NewSecurePass456!")
    user_repo.get_user_by_id.assert_awaited_once_with(token.user_id)
    repo.update_user_password.assert_awaited_once_with(user, "hashed-new")
    repo.delete_existing_tokens.assert_awaited_once_with(user_id=user.id)
    assert db.commit_calls == 1


async def test_reset_password_guest_happy_path(mocker):
    guest = make_account(kind="guest")
    token = make_token(guest_id=guest.id)
    repo = mocker.AsyncMock()
    repo.get_token_by_hash.return_value = token
    guest_repo = mocker.AsyncMock()
    guest_repo.get_guest_by_id.return_value = guest
    auth_service = mocker.MagicMock()
    auth_service.get_password_hash.return_value = "hashed-new"
    db = FakeDB()
    svc = build_service(
        mocker,
        db=db,
        password_reset_repo=repo,
        guest_repo=guest_repo,
        auth_service=auth_service,
    )

    await svc.reset_password("raw-token", "NewSecurePass456!")

    guest_repo.get_guest_by_id.assert_awaited_once_with(token.guest_id)
    repo.update_guest_password.assert_awaited_once_with(guest, "hashed-new")
    repo.delete_existing_tokens.assert_awaited_once_with(guest_id=guest.id)
    assert db.commit_calls == 1


async def test_reset_password_token_for_missing_user(mocker):
    token = make_token(user_id=uuid.uuid4())
    repo = mocker.AsyncMock()
    repo.get_token_by_hash.return_value = token
    user_repo = mocker.AsyncMock()
    user_repo.get_user_by_id.return_value = None
    db = FakeDB()
    svc = build_service(
        mocker, db=db, password_reset_repo=repo, user_repo=user_repo
    )

    with pytest.raises(InvalidResetTokenException):
        await svc.reset_password("raw-token", "NewSecurePass456!")

    assert db.rollback_calls == 1


async def test_reset_password_token_for_missing_guest(mocker):
    token = make_token(guest_id=uuid.uuid4())
    repo = mocker.AsyncMock()
    repo.get_token_by_hash.return_value = token
    guest_repo = mocker.AsyncMock()
    guest_repo.get_guest_by_id.return_value = None
    db = FakeDB()
    svc = build_service(
        mocker, db=db, password_reset_repo=repo, guest_repo=guest_repo
    )

    with pytest.raises(InvalidResetTokenException):
        await svc.reset_password("raw-token", "NewSecurePass456!")


async def test_reset_password_repository_error_re_raises(mocker):
    repo = mocker.AsyncMock()
    repo.get_token_by_hash.side_effect = RepositoryException("boom")
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)

    with pytest.raises(RepositoryException):
        await svc.reset_password("raw-token", "NewSecurePass456!")

    assert db.rollback_calls == 1


async def test_reset_password_unexpected_error_becomes_service_exception(mocker):
    repo = mocker.AsyncMock()
    repo.get_token_by_hash.side_effect = ValueError("boom")
    db = FakeDB()
    svc = build_service(mocker, db=db, password_reset_repo=repo)

    with pytest.raises(ServiceException):
        await svc.reset_password("raw-token", "NewSecurePass456!")

    assert db.rollback_calls == 1


# ═══════════════════════════════════════════════════════════════════════════
# change_password
# ═══════════════════════════════════════════════════════════════════════════

async def test_change_password_wrong_current_password(mocker):
    account = make_account()
    auth_service = mocker.MagicMock()
    auth_service.verify_password.return_value = False
    repo = mocker.AsyncMock()
    db = FakeDB()
    svc = build_service(
        mocker, db=db, password_reset_repo=repo, auth_service=auth_service
    )

    with pytest.raises(InvalidPasswordException):
        await svc.change_password(account, "wrong", "NewSecurePass456!", "user")

    assert db.rollback_calls == 1
    repo.update_user_password.assert_not_awaited()
    repo.update_guest_password.assert_not_awaited()


async def test_change_password_guest_happy_path(mocker):
    guest = make_account(kind="guest")
    auth_service = mocker.MagicMock()
    auth_service.verify_password.return_value = True
    auth_service.get_password_hash.return_value = "hashed-new"
    repo = mocker.AsyncMock()
    db = FakeDB()
    svc = build_service(
        mocker, db=db, password_reset_repo=repo, auth_service=auth_service
    )

    await svc.change_password(guest, "old", "NewSecurePass456!", "guest")

    auth_service.get_password_hash.assert_called_once_with("NewSecurePass456!")
    repo.update_guest_password.assert_awaited_once_with(guest, "hashed-new")
    repo.update_user_password.assert_not_awaited()
    assert db.commit_calls == 1


async def test_change_password_user_happy_path(mocker):
    user = make_account()
    auth_service = mocker.MagicMock()
    auth_service.verify_password.return_value = True
    auth_service.get_password_hash.return_value = "hashed-new"
    repo = mocker.AsyncMock()
    db = FakeDB()
    svc = build_service(
        mocker, db=db, password_reset_repo=repo, auth_service=auth_service
    )

    await svc.change_password(user, "old", "NewSecurePass456!", "user")

    repo.update_user_password.assert_awaited_once_with(user, "hashed-new")
    repo.update_guest_password.assert_not_awaited()
    assert db.commit_calls == 1


async def test_change_password_invalid_account_type(mocker):
    account = make_account()
    auth_service = mocker.MagicMock()
    auth_service.verify_password.return_value = True
    repo = mocker.AsyncMock()
    db = FakeDB()
    svc = build_service(
        mocker, db=db, password_reset_repo=repo, auth_service=auth_service
    )

    with pytest.raises(InvalidAccountTypeException):
        await svc.change_password(account, "old", "NewSecurePass456!", "staff")

    assert db.rollback_calls == 1
    assert db.commit_calls == 0


async def test_change_password_repository_error_re_raises(mocker):
    account = make_account()
    auth_service = mocker.MagicMock()
    auth_service.verify_password.return_value = True
    repo = mocker.AsyncMock()
    repo.update_user_password.side_effect = RepositoryException("boom")
    db = FakeDB()
    svc = build_service(
        mocker, db=db, password_reset_repo=repo, auth_service=auth_service
    )

    with pytest.raises(RepositoryException):
        await svc.change_password(account, "old", "NewSecurePass456!", "user")

    assert db.rollback_calls == 1


async def test_change_password_unexpected_error_becomes_service_exception(mocker):
    account = make_account()
    auth_service = mocker.MagicMock()
    auth_service.verify_password.return_value = True
    auth_service.get_password_hash.side_effect = ValueError("boom")
    repo = mocker.AsyncMock()
    db = FakeDB()
    svc = build_service(
        mocker, db=db, password_reset_repo=repo, auth_service=auth_service
    )

    with pytest.raises(ServiceException):
        await svc.change_password(account, "old", "NewSecurePass456!", "user")

    assert db.rollback_calls == 1


async def test_verify_password_unexpected_error_becomes_service_exception(mocker):
    account = make_account()
    auth_service = mocker.MagicMock()
    auth_service.verify_password.side_effect = ValueError("boom")
    db = FakeDB()
    svc = build_service(mocker, db=db, auth_service=auth_service)

    with pytest.raises(ServiceException):
        await svc.change_password(account, "old", "NewSecurePass456!", "user")

    assert db.rollback_calls == 1