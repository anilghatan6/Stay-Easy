import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.superadmin.models.platform_audit_log_model import PlatformAuditLog
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class AuditRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        actor_id: uuid.UUID,
        actor_email: str,
        action: str,
        target_type: str,
        target_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> PlatformAuditLog:
        try:
            entry = PlatformAuditLog(
                actor_id=actor_id,
                actor_email=actor_email,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
                ip_address=ip_address,
            )
            self.db.add(entry)
            await self.db.flush()
            return entry
        except SQLAlchemyError as e:
            logger.error(f"[AuditRepository] Failed to log audit entry: {e}")
            raise RepositoryException("Failed to log audit entry.")

    async def get_logs_for_target(
        self,
        target_type: str,
        target_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PlatformAuditLog], int]:
        try:
            stmt = (
                select(PlatformAuditLog)
                .where(
                    PlatformAuditLog.target_type == target_type,
                    PlatformAuditLog.target_id == target_id,
                )
                .order_by(PlatformAuditLog.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            logs = list(result.scalars().all())

            count_stmt = (
                select(func.count())
                .select_from(PlatformAuditLog)
                .where(
                    PlatformAuditLog.target_type == target_type,
                    PlatformAuditLog.target_id == target_id,
                )
            )
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar_one()

            return logs, total
        except SQLAlchemyError as e:
            logger.error(f"[AuditRepository] Failed to fetch audit logs: {e}")
            raise RepositoryException("Failed to fetch audit logs.")

    async def get_all_logs(
        self, skip: int = 0, limit: int = 50
    ) -> tuple[list[PlatformAuditLog], int]:
        try:
            stmt = (
                select(PlatformAuditLog)
                .order_by(PlatformAuditLog.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            logs = list(result.scalars().all())

            count_stmt = select(func.count()).select_from(PlatformAuditLog)
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar_one()

            return logs, total
        except SQLAlchemyError as e:
            logger.error(f"[AuditRepository] Failed to fetch all audit logs: {e}")
            raise RepositoryException("Failed to fetch audit logs.")
