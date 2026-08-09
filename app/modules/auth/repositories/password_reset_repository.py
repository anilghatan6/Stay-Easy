from datetime import UTC
import uuid
from datetime import datetime
from sqlalchemy import select, delete, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.password_reset_token_model import PasswordResetToken
from app.modules.auth.models.users_model import User
from app.modules.auth.models.guests_model import Guest
from app.utils.exceptions import RepositoryException,InvalidPasswordException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class PasswordResetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Account lookup across both tables ──────────────────────────────────────

    async def find_user_by_email(self, email: str) -> User | None:
        try:
            stmt = select(User).where(func.lower(User.email) == email.lower())
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(
                f"[PasswordResetRepository] Failed to look up user by email: {e}"
            )
            raise RepositoryException(
                "Could not process request. Please try again."
            ) from e

    async def find_guest_by_email(self, email: str) -> Guest | None:
        try:
            stmt = select(Guest).where(func.lower(Guest.email) == email.lower())
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(
                f"[PasswordResetRepository] Failed to look up guest by email: {e}"
            )
            raise RepositoryException(
                "Could not process request. Please try again."
            ) from e

    # ─── Token lifecycle ──────────────────────────────────────

    async def delete_existing_tokens(
        self, user_id: uuid.UUID | None = None, guest_id: uuid.UUID | None = None
    ) -> None:
        try:
            if user_id is not None:
                stmt = delete(PasswordResetToken).where(
                    PasswordResetToken.user_id == user_id
                )
            else:
                stmt = delete(PasswordResetToken).where(
                    PasswordResetToken.guest_id == guest_id
                )
            await self.db.execute(stmt)
        except SQLAlchemyError as e:
            logger.error(
                f"[PasswordResetRepository] Failed to delete existing tokens: {e}"
            )
            raise RepositoryException(
                "Could not process request. Please try again."
            ) from e

    async def create_token(
        self,
        temp_password_hash: str,
        expires_at: datetime,
        user_id: uuid.UUID | None = None,
        guest_id: uuid.UUID | None = None,
    ) -> PasswordResetToken:
        try:
            reset_token = PasswordResetToken(
                id=uuid.uuid4(),
                user_id=user_id,
                guest_id=guest_id,
                temp_password_hash=temp_password_hash,
                expires_at=expires_at,
            )
            self.db.add(reset_token)
            await self.db.flush()
            return reset_token
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to create reset token: {e}")
            raise RepositoryException(
                "Could not process request. Please try again."
            ) from e

    async def get_token_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        try:
            stmt = select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to fetch token: {e}")
            raise RepositoryException(
                "Could not process request. Please try again."
            ) from e

    async def delete_token(self, token: PasswordResetToken) -> None:
        try:
            await self.db.delete(token)
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to delete token: {e}")
            raise RepositoryException(
                "Could not process request. Please try again."
            ) from e

    async def update_user_password(self, user: User, hashed_password: str) -> None:
        try:
            user.hashed_password = hashed_password
        except SQLAlchemyError as e:
            logger.error(
                f"[PasswordResetRepository] Failed to update user password: {e}"
            )
            raise RepositoryException(
                "Could not update password. Please try again."
            ) from e

    async def update_guest_password(self, guest: Guest, hashed_password: str) -> None:
        try:
            guest.hashed_password = hashed_password
        except SQLAlchemyError as e:
            logger.error(
                f"[PasswordResetRepository] Failed to update guest password: {e}"
            )
            raise RepositoryException(
                "Could not update password. Please try again."
            ) from e

    async def get_active_temp_password_token(
        self, user_id: uuid.UUID | None = None, guest_id: uuid.UUID | None = None
    ) -> PasswordResetToken | None:
        try:
            if user_id is not None:
                stmt = select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user_id
                )
            else:
                stmt = select(PasswordResetToken).where(
                    PasswordResetToken.guest_id == guest_id
                )

            result = await self.db.execute(stmt)
            token = result.scalar_one_or_none()

            if token is None or not token.is_valid:
                return None
            return token

        except SQLAlchemyError as e:
            logger.error(
                "[PasswordResetRepository] Failed to fetch temp password token"
            )
            raise RepositoryException(f"Could not process request:{e}")

    async def mark_token_used(self, token: PasswordResetToken) -> None:
        try:
            token.used_at = datetime.now(UTC)
        except SQLAlchemyError as e:
            logger.error("[PasswordResetRepository] Failed to mark token used")
            raise RepositoryException(f"Could not process request:{e}")

    async def get_latest_token(
        self, user_id: uuid.UUID | None = None, guest_id: uuid.UUID | None = None
    ) -> PasswordResetToken | None:
        """
        Fetches the most recent token for this account, regardless of validity —
        unlike get_active_temp_password_token, this returns even expired/used
        tokens so the caller can distinguish WHY a login attempt should fail.
        """
        try:
            if user_id is not None:
                stmt = (
                    select(PasswordResetToken)
                    .where(PasswordResetToken.user_id == user_id)
                    .order_by(PasswordResetToken.created_at.desc())
                    .limit(1)
                )
            else:
                stmt = (
                    select(PasswordResetToken)
                    .where(PasswordResetToken.guest_id == guest_id)
                    .order_by(PasswordResetToken.created_at.desc())
                    .limit(1)
                )
            result = await self.db.execute(stmt)
            token_obj= result.scalar_one_or_none()
            if token_obj is None:
                logger.warning(
                    f"[PasswordResetService] must_change_password=True but no token found "
                    f"(user_id={user_id}, guest_id={guest_id})"
                )
                raise InvalidPasswordException("Invalid Credentials")
            return token_obj

        except SQLAlchemyError as e:
            logger.error(
                f"[PasswordResetRepository] Failed to fetch latest token: {e}"
            )
            raise RepositoryException("Could not process request.") from e
