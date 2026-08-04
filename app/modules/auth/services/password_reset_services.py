import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, UTC
from app.modules.auth.repositories.password_reset_repository import (
    PasswordResetRepository,
)
from app.modules.auth.repositories.users_repo import UserRepository
from app.modules.auth.repositories.guests_repo import GuestRepository
from app.modules.auth.services.auth_services import AuthService
from app.modules.auth.services.mail_services import send_password_reset_email
from app.utils.exceptions import (
    ServiceException,
    RepositoryException,
    EmailDeliveryError,
    InvalidResetTokenException,
    InvalidPasswordException,
    InvalidAccountTypeException,
)
from app.modules.auth.models import Guest, User
from app.utils.logging import LoggerFactory
# from pwdlib import PasswordHash

import os

logger = LoggerFactory.get_logger(__name__)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# def get_hash_password(password: str) -> str:
#     password_hash = PasswordHash.recommended()
#     return password_hash.hash(password)


class PasswordResetService:
    def __init__(
        self,
        db,
        password_reset_repo: PasswordResetRepository,
        user_repo: UserRepository,
        guest_repo: GuestRepository,
        auth_service: AuthService,
    ):
        self.db = db
        self.password_reset_repo = password_reset_repo
        self.user_repo = user_repo
        self.guest_repo = guest_repo
        self.auth_service = auth_service

    async def request_password_reset(self, email: str) -> None:
        """
        Looks up the email across both User and Guest tables, issues a reset
        token for whichever one matches, and sends the email. Always returns
        the same generic outcome regardless of whether an account was found —
        callers should never learn from the response whether an email exists
        in the system (prevents account enumeration).
        """
        try:
            user = await self.password_reset_repo.find_user_by_email(email)
            guest = None

            if user is None:
                guest = await self.password_reset_repo.find_guest_by_email(email)

            if user is None and guest is None:
                logger.info(
                    f"[PasswordResetService] No account found for {email} — silently no-op"
                )
                return  # deliberately silent — do not leak account existence

            token = generate_reset_token()
            token_hash = hash_reset_token(token)
            expires_at = datetime.now(UTC) + timedelta(
                minutes=int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", 15))
            )

            if user is not None:
                await self.password_reset_repo.delete_existing_tokens(user_id=user.id)
                await self.password_reset_repo.create_token(
                    token_hash=token_hash, expires_at=expires_at, user_id=user.id
                )
                await self.db.commit()

                recipient_email = user.email
                recipient_name = user.full_name

            else:
                await self.password_reset_repo.delete_existing_tokens(guest_id=guest.id)
                await self.password_reset_repo.create_token(
                    token_hash=token_hash, expires_at=expires_at, guest_id=guest.id
                )
                await self.db.commit()

                recipient_email = guest.email
                recipient_name = guest.full_name

            try:
                await send_password_reset_email(
                    to_email=recipient_email, username=recipient_name, token=token
                )
            except EmailDeliveryError as e:
                # Token was created successfully — email failure shouldn't be
                # surfaced to the caller (would leak account existence anyway).
                logger.error(
                    f"[PasswordResetService] Reset email failed for {email}: {e}"
                )

        except RepositoryException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[PasswordResetService] Unexpected error processing reset for {email}: {e}"
            )
            raise ServiceException("Could not process request. Please try again.")

    async def reset_password(self, token: str, new_password: str) -> None:
        try:
            token_hash = hash_reset_token(token)
            reset_token = await self.password_reset_repo.get_token_by_hash(token_hash)

            if reset_token is None:
                raise InvalidResetTokenException("Invalid or expired reset token")

            if reset_token.expires_at < datetime.now(UTC):
                await self.password_reset_repo.delete_token(reset_token)
                await self.db.commit()
                raise InvalidResetTokenException("Invalid or expired reset token")

            if reset_token.used_at is not None:
                raise InvalidResetTokenException("Invalid or expired reset token")

            hashed_password = self.auth_service.get_password_hash(new_password)

            if reset_token.user_id is not None:
                user = await self.user_repo.get_user_by_id(reset_token.user_id)
                if user is None:
                    raise InvalidResetTokenException("Invalid or expired reset token")
                await self.password_reset_repo.update_user_password(
                    user, hashed_password
                )
                await self.password_reset_repo.delete_existing_tokens(user_id=user.id)

            else:
                guest = await self.guest_repo.get_guest_by_id(reset_token.guest_id)
                if guest is None:
                    raise InvalidResetTokenException("Invalid or expired reset token")
                await self.password_reset_repo.update_guest_password(
                    guest, hashed_password
                )
                await self.password_reset_repo.delete_existing_tokens(guest_id=guest.id)

            await self.db.commit()

        except InvalidResetTokenException:
            await self.db.rollback()
            raise
        except RepositoryException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[PasswordResetService] Unexpected error resetting password: {e}"
            )
            raise ServiceException("Could not reset password. Please try again.")

    def _verify_password(self, plain_password: str, hashed_password: str):
        try:
            # Securely verify using passlib/bcrypt via your auth service utility
            if not self.auth_service.verify_password(plain_password, hashed_password):
                raise InvalidPasswordException("Current Password is incorrect")
            return True

        except InvalidPasswordException:
            raise
        except Exception as e:
            logger.error(
                f"[PasswordResetService] Unexpected error hashing verification match: {e}"
            )
            raise ServiceException("Could not verify password. Please try again.")

    async def change_password(
        self, account: User | Guest, current_password: str, new_password: str, role: str
    ) -> None:
        try:
            await self._verify_password(current_password, account.hashed_password)
            hashed_new_password = self.auth_service.get_password_hash(new_password)
            if role == "guest":
                await self.password_reset_repo.update_guest_password(
                    account, hashed_new_password
                )
            elif role == "user":
                await self.password_reset_repo.update_user_password(
                    account, hashed_new_password
                )

            else:
                raise InvalidAccountTypeException("Invalid account type provided.")
            await self.db.commit()

        except (
            InvalidAccountTypeException,
            InvalidPasswordException,
            RepositoryException,
        ):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[PasswordResetService] Unexpected error changing password: {e}"
            )
            raise ServiceException("Could not change password. Please try again.")
