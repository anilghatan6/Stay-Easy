import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.superadmin.models.feature_flag_model import FeatureFlag
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class FeatureFlagRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_flag(
        self,
        name: str,
        key: str,
        description: Optional[str] = None,
        is_enabled: bool = False,
        created_by: Optional[uuid.UUID] = None,
    ) -> FeatureFlag:
        try:
            flag = FeatureFlag(
                name=name,
                key=key,
                description=description,
                is_enabled=is_enabled,
                created_by=created_by,
            )
            self.db.add(flag)
            await self.db.flush()
            await self.db.refresh(flag)
            return flag
        except SQLAlchemyError as e:
            logger.error(f"[FeatureFlagRepo] Failed to create flag: {e}")
            raise RepositoryException("Failed to create feature flag.")

    async def get_by_id(self, flag_id: uuid.UUID) -> Optional[FeatureFlag]:
        try:
            stmt = select(FeatureFlag).where(FeatureFlag.id == flag_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[FeatureFlagRepo] Failed to fetch flag: {e}")
            raise RepositoryException("Failed to fetch feature flag.")

    async def get_by_key(self, key: str) -> Optional[FeatureFlag]:
        try:
            stmt = select(FeatureFlag).where(FeatureFlag.key == key)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[FeatureFlagRepo] Failed to fetch flag by key: {e}")
            raise RepositoryException("Failed to fetch feature flag.")

    async def list_flags(self) -> list[FeatureFlag]:
        try:
            stmt = select(FeatureFlag).order_by(FeatureFlag.created_at.desc())
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"[FeatureFlagRepo] Failed to list flags: {e}")
            raise RepositoryException("Failed to list feature flags.")

    async def update_flag(self, flag_id: uuid.UUID, update_data: dict) -> Optional[FeatureFlag]:
        try:
            flag = await self.get_by_id(flag_id)
            if flag is None:
                return None
            for field, value in update_data.items():
                setattr(flag, field, value)
            await self.db.flush()
            await self.db.refresh(flag)
            return flag
        except SQLAlchemyError as e:
            logger.error(f"[FeatureFlagRepo] Failed to update flag: {e}")
            raise RepositoryException("Failed to update feature flag.")

    async def delete_flag(self, flag_id: uuid.UUID) -> bool:
        try:
            flag = await self.get_by_id(flag_id)
            if flag is None:
                return False
            await self.db.delete(flag)
            await self.db.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"[FeatureFlagRepo] Failed to delete flag: {e}")
            raise RepositoryException("Failed to delete feature flag.")

    async def is_enabled(self, key: str) -> bool:
        try:
            flag = await self.get_by_key(key)
            return flag.is_enabled if flag else False
        except SQLAlchemyError:
            return False
