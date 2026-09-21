import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.users_model import User
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

ADMIN_ROLES = {"admin", "manager", "front_desk", "housekeeping", "maintenance", "waiter", "kitchen"}


class AdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[AdminRepository] Failed to fetch user {user_id}: {e}")
            raise RepositoryException("Failed to fetch user.")

    async def get_by_email(self, email: str) -> Optional[User]:
        try:
            stmt = select(User).where(User.email == email)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[AdminRepository] Failed to fetch user by email: {e}")
            raise RepositoryException("Failed to fetch user.")

    async def create_admin(
        self,
        email: str,
        full_name: str,
        phone: Optional[str],
        hashed_password: str,
    ) -> User:
        try:
            user = User(
                email=email,
                full_name=full_name,
                phone=phone,
                hashed_password=hashed_password,
                role="admin",
                is_active=True,
                must_change_password=False,
            )
            self.db.add(user)
            await self.db.flush()
            await self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            logger.error(f"[AdminRepository] Failed to create admin: {e}")
            raise RepositoryException("Failed to create admin account.")

    async def update_admin(self, user_id: uuid.UUID, update_data: dict) -> Optional[User]:
        try:
            user = await self.get_by_id(user_id)
            if user is None:
                return None
            for field, value in update_data.items():
                setattr(user, field, value)
            await self.db.flush()
            await self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            logger.error(f"[AdminRepository] Failed to update admin {user_id}: {e}")
            raise RepositoryException("Failed to update admin account.")

    async def delete_admin(self, user_id: uuid.UUID) -> bool:
        try:
            user = await self.get_by_id(user_id)
            if user is None:
                return False
            user.is_active = False
            await self.db.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"[AdminRepository] Failed to delete admin {user_id}: {e}")
            raise RepositoryException("Failed to delete admin account.")

    async def list_admins(
        self, skip: int = 0, limit: int = 50
    ) -> tuple[list[User], int]:
        try:
            stmt = (
                select(User)
                .where(User.role.in_(ADMIN_ROLES))
                .order_by(User.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            admins = list(result.scalars().all())

            count_stmt = (
                select(func.count())
                .select_from(User)
                .where(User.role.in_(ADMIN_ROLES))
            )
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar_one()

            return admins, total
        except SQLAlchemyError as e:
            logger.error(f"[AdminRepository] Failed to list admins: {e}")
            raise RepositoryException("Failed to list admins.")
