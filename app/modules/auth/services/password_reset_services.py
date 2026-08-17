import hashlib
import secrets
import string
import uuid
from datetime import datetime, timedelta, UTC
from app.modules.auth.repositories.password_reset_repository import (
    PasswordResetRepository,
)
from app.modules.auth.repositories.users_repo import UserRepository
from app.modules.auth.repositories.guests_repo import GuestRepository
from app.modules.auth.services.auth_services import AuthService
from app.utils.mail_services import send_password_reset_email
from app.utils.exceptions import (
    ServiceException,
    RepositoryException,
    EmailDeliveryError,
    InvalidResetTokenException,
    InvalidPasswordException,
    InvalidAccountTypeException,
    TempPasswordAlreadyUsedError,
    TempPasswordExpiredError

)
from app.modules.auth.models import Guest, User
from app.utils.logging import LoggerFactory
from app.config.settings_config import settings


logger = LoggerFactory.get_logger(__name__)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


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

    def _generate_temp_password(self, length: int = 8) -> str:
        """Generates a secure temporary password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    async def request_password_reset(self, email: str) -> None:
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

            temp_password = self._generate_temp_password(8)
            # hashed_password = self.auth_service.get_password_hash(temp_password)
            temp_password_hash = self.auth_service.get_password_hash(temp_password)  # same hash, stored for token lookup
            expires_at = datetime.now(UTC) + timedelta(
                minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
            )

            if user is not None:
                await self.password_reset_repo.delete_existing_tokens(user_id=user.id)
                await self.password_reset_repo.update_user_password(user, temp_password_hash)
                user.must_change_password = True
                await self.password_reset_repo.create_token(
                    temp_password_hash=temp_password_hash,
                    expires_at=expires_at,
                    user_id=user.id,
                )
                await self.db.commit()
                recipient_email = user.email
                recipient_name = user.full_name

            else:
                await self.password_reset_repo.delete_existing_tokens(guest_id=guest.id)
                await self.password_reset_repo.update_guest_password(guest, temp_password_hash)
                guest.must_change_password = True
                await self.password_reset_repo.create_token(
                    temp_password_hash=temp_password_hash,
                    expires_at=expires_at,
                    guest_id=guest.id,
                )
                await self.db.commit()
                recipient_email = guest.email
                recipient_name = guest.full_name

            try:
                await send_password_reset_email(
                    to_email=recipient_email,
                    username=recipient_name,
                    temp_password=temp_password,
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

            expires_at = reset_token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at < datetime.now(UTC):
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

    async def _verify_password(self, account: User | Guest, plain_password: str):
        try:
            if not self.auth_service.verify_password(
                plain_password, account.hashed_password
            ):
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
            await self._verify_password(account, current_password)
            hashed_new_password = self.auth_service.get_password_hash(new_password)
            if role == "guest":
                await self.password_reset_repo.update_guest_password(
                    account, hashed_new_password
                )
                account.must_change_password = False
            elif role == "user":
                await self.password_reset_repo.update_user_password(
                    account, hashed_new_password
                )
                account.must_change_password = False

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

    async def validate_and_consume_temp_password(
        self, user_id: uuid.UUID | None = None, guest_id: uuid.UUID | None = None
    ) -> None:
        """
        Called during login, AFTER password hash verification succeeds,
        ONLY when the account's must_change_password flag is True.
        Raises a specific exception if the temp password is expired or
        already used — otherwise consumes the token (one-time use enforced).
        """
        token = await self.password_reset_repo.get_latest_token(user_id=user_id, guest_id=guest_id)

        if token.used_at is not None:
            logger.warning(f"[PasswordResetService] Rejected reuse of already-used temp password token {token.id}")
            raise TempPasswordAlreadyUsedError(
                "This temporary password has already been used. Please request a new one."
            )

        if token.expires_at <= datetime.now(UTC):
            logger.warning(f"[PasswordResetService] Rejected expired temp password token {token.id}")
            raise TempPasswordExpiredError(
                "This temporary password has expired. Please request a new one."
            )

        # Valid — consume it now, so it can never be used again
        await self.password_reset_repo.mark_token_used(token)
        await self.db.commit()
