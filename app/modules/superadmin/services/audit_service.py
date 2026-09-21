import uuid
from typing import Optional

from app.modules.superadmin.repositories.audit_repository import AuditRepository
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class AuditService:
    def __init__(self, audit_repo: AuditRepository):
        self.audit_repo = audit_repo

    async def log(
        self,
        actor_id: uuid.UUID,
        actor_email: str,
        action: str,
        target_type: str,
        target_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ):
        await self.audit_repo.log(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=ip_address,
        )

    async def get_logs_for_target(
        self, target_type: str, target_id: uuid.UUID, skip: int = 0, limit: int = 50
    ):
        return await self.audit_repo.get_logs_for_target(target_type, target_id, skip, limit)

    async def get_all_logs(self, skip: int = 0, limit: int = 50):
        return await self.audit_repo.get_all_logs(skip, limit)
