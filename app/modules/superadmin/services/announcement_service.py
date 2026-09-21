import uuid
from typing import Optional

from app.modules.superadmin.repositories.announcement_repository import AnnouncementRepository
from app.modules.superadmin.repositories.audit_repository import AuditRepository
from app.modules.auth.models.users_model import User
from app.utils.exceptions import ServiceException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class AnnouncementService:
    def __init__(
        self,
        db,
        announcement_repo: AnnouncementRepository,
        audit_repo: AuditRepository,
    ):
        self.db = db
        self.announcement_repo = announcement_repo
        self.audit_repo = audit_repo

    async def create_announcement(
        self,
        title: str,
        message: str,
        priority: str = "INFO",
        target: str = "ALL",
        target_admin_ids: Optional[list] = None,
        send_email: bool = False,
        actor: User = None,
        ip_address: Optional[str] = None,
    ):
        announcement = await self.announcement_repo.create_announcement(
            title=title,
            message=message,
            priority=priority,
            target=target,
            target_admin_ids=target_admin_ids,
            send_email=send_email,
            created_by=actor.id if actor else None,
        )

        if actor:
            await self.audit_repo.log(
                actor_id=actor.id,
                actor_email=actor.email,
                action="create_announcement",
                target_type="announcement",
                target_id=announcement.id,
                details={"title": title, "target": target, "send_email": send_email},
                ip_address=ip_address,
            )
        await self.db.commit()
        logger.info(f"[AnnouncementService] Announcement created: {announcement.id}")
        return announcement

    async def list_announcements(self, skip: int = 0, limit: int = 50):
        return await self.announcement_repo.list_announcements(skip, limit)

    async def delete_announcement(
        self,
        announcement_id: uuid.UUID,
        actor: User = None,
        ip_address: Optional[str] = None,
    ):
        deleted = await self.announcement_repo.delete_announcement(announcement_id)
        if not deleted:
            raise ServiceException("Announcement not found.")

        if actor:
            await self.audit_repo.log(
                actor_id=actor.id,
                actor_email=actor.email,
                action="delete_announcement",
                target_type="announcement",
                target_id=announcement_id,
                ip_address=ip_address,
            )
        await self.db.commit()
        logger.info(f"[AnnouncementService] Announcement deleted: {announcement_id}")
