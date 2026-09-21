import uuid
from typing import Optional

from app.modules.superadmin.repositories.feature_flag_repository import FeatureFlagRepository
from app.modules.superadmin.repositories.audit_repository import AuditRepository
from app.modules.auth.models.users_model import User
from app.utils.exceptions import ServiceException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class FeatureFlagService:
    def __init__(
        self,
        db,
        feature_flag_repo: FeatureFlagRepository,
        audit_repo: AuditRepository,
    ):
        self.db = db
        self.feature_flag_repo = feature_flag_repo
        self.audit_repo = audit_repo

    async def create_flag(
        self,
        name: str,
        key: str,
        description: Optional[str] = None,
        is_enabled: bool = False,
        actor: User = None,
        ip_address: Optional[str] = None,
    ):
        existing = await self.feature_flag_repo.get_by_key(key)
        if existing:
            raise ServiceException(f"Feature flag with key '{key}' already exists.")

        flag = await self.feature_flag_repo.create_flag(
            name=name,
            key=key,
            description=description,
            is_enabled=is_enabled,
            created_by=actor.id if actor else None,
        )

        if actor:
            await self.audit_repo.log(
                actor_id=actor.id,
                actor_email=actor.email,
                action="create_feature_flag",
                target_type="feature_flag",
                target_id=flag.id,
                details={"name": name, "key": key, "is_enabled": is_enabled},
                ip_address=ip_address,
            )
        await self.db.commit()
        logger.info(f"[FeatureFlagService] Flag created: {flag.id} ({key})")
        return flag

    async def get_flag(self, flag_id: uuid.UUID):
        flag = await self.feature_flag_repo.get_by_id(flag_id)
        if flag is None:
            raise ServiceException("Feature flag not found.")
        return flag

    async def list_flags(self):
        return await self.feature_flag_repo.list_flags()

    async def update_flag(
        self,
        flag_id: uuid.UUID,
        update_data: dict,
        actor: User = None,
        ip_address: Optional[str] = None,
    ):
        flag = await self.feature_flag_repo.update_flag(flag_id, update_data)
        if flag is None:
            raise ServiceException("Feature flag not found.")

        if actor:
            await self.audit_repo.log(
                actor_id=actor.id,
                actor_email=actor.email,
                action="update_feature_flag",
                target_type="feature_flag",
                target_id=flag_id,
                details=update_data,
                ip_address=ip_address,
            )
        await self.db.commit()
        logger.info(f"[FeatureFlagService] Flag updated: {flag_id}")
        return flag

    async def delete_flag(
        self,
        flag_id: uuid.UUID,
        actor: User = None,
        ip_address: Optional[str] = None,
    ):
        deleted = await self.feature_flag_repo.delete_flag(flag_id)
        if not deleted:
            raise ServiceException("Feature flag not found.")

        if actor:
            await self.audit_repo.log(
                actor_id=actor.id,
                actor_email=actor.email,
                action="delete_feature_flag",
                target_type="feature_flag",
                target_id=flag_id,
                ip_address=ip_address,
            )
        await self.db.commit()
        logger.info(f"[FeatureFlagService] Flag deleted: {flag_id}")

    async def is_enabled(self, key: str) -> bool:
        return await self.feature_flag_repo.is_enabled(key)
