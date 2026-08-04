import uuid
from datetime import datetime
from sqlalchemy import select, delete, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.password_reset_token_model import PasswordResetToken
from app.modules.auth.models.users_model import User
from app.modules.auth.models.guests_model import Guest
from app.utils.exceptions import RepositoryException
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
            logger.error(f"[PasswordResetRepository] Failed to look up user by email: {e}")
            raise RepositoryException("Could not process request. Please try again.") from e

    async def find_guest_by_email(self, email: str) -> Guest | None:
        try:
            stmt = select(Guest).where(func.lower(Guest.email) == email.lower())
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to look up guest by email: {e}")
            raise RepositoryException("Could not process request. Please try again.") from e

    # ─── Token lifecycle ──────────────────────────────────────

    async def delete_existing_tokens(
        self, user_id: uuid.UUID | None = None, guest_id: uuid.UUID | None = None
    ) -> None:
        try:
            if user_id is not None:
                stmt = delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
            else:
                stmt = delete(PasswordResetToken).where(PasswordResetToken.guest_id == guest_id)
            await self.db.execute(stmt)
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to delete existing tokens: {e}")
            raise RepositoryException("Could not process request. Please try again.") from e

    async def create_token(
        self,
        token_hash: str,
        expires_at: datetime,
        user_id: uuid.UUID | None = None,
        guest_id: uuid.UUID | None = None,
    ) -> PasswordResetToken:
        try:
            reset_token = PasswordResetToken(
                id=uuid.uuid4(),
                user_id=user_id,
                guest_id=guest_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            self.db.add(reset_token)
            await self.db.flush()
            return reset_token
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to create reset token: {e}")
            raise RepositoryException("Could not process request. Please try again.") from e

    async def get_token_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        try:
            stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to fetch token: {e}")
            raise RepositoryException("Could not process request. Please try again.") from e

    async def delete_token(self, token: PasswordResetToken) -> None:
        try:
            await self.db.delete(token)
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to delete token: {e}")
            raise RepositoryException("Could not process request. Please try again.") from e

    async def update_user_password(self, user: User, hashed_password: str) -> None:
        try:
            user.hashed_password = hashed_password
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to update user password: {e}")
            raise RepositoryException("Could not update password. Please try again.") from e

    async def update_guest_password(self, guest: Guest, hashed_password: str) -> None:
        try:
            guest.hashed_password = hashed_password
        except SQLAlchemyError as e:
            logger.error(f"[PasswordResetRepository] Failed to update guest password: {e}")
            raise RepositoryException("Could not update password. Please try again.") from e