import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.superadmin.models.announcement_model import Announcement
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class AnnouncementRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_announcement(
        self,
        title: str,
        message: str,
        priority: str = "INFO",
        target: str = "ALL",
        target_admin_ids: Optional[list] = None,
        send_email: bool = False,
        created_by: Optional[uuid.UUID] = None,
    ) -> Announcement:
        try:
            announcement = Announcement(
                title=title,
                message=message,
                priority=priority,
                target=target,
                target_admin_ids=target_admin_ids,
                send_email=send_email,
                created_by=created_by,
            )
            self.db.add(announcement)
            await self.db.flush()
            await self.db.refresh(announcement)
            return announcement
        except SQLAlchemyError as e:
            logger.error(f"[AnnouncementRepo] Failed to create announcement: {e}")
            raise RepositoryException("Failed to create announcement.")

    async def get_by_id(self, announcement_id: uuid.UUID) -> Optional[Announcement]:
        try:
            stmt = select(Announcement).where(Announcement.id == announcement_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[AnnouncementRepo] Failed to fetch announcement: {e}")
            raise RepositoryException("Failed to fetch announcement.")

    async def list_announcements(
        self, skip: int = 0, limit: int = 50
    ) -> tuple[list[Announcement], int]:
        try:
            stmt = (
                select(Announcement)
                .order_by(Announcement.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            announcements = list(result.scalars().all())

            count_stmt = select(func.count()).select_from(Announcement)
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar_one()

            return announcements, total
        except SQLAlchemyError as e:
            logger.error(f"[AnnouncementRepo] Failed to list announcements: {e}")
            raise RepositoryException("Failed to list announcements.")

    async def delete_announcement(self, announcement_id: uuid.UUID) -> bool:
        try:
            announcement = await self.get_by_id(announcement_id)
            if announcement is None:
                return False
            await self.db.delete(announcement)
            await self.db.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"[AnnouncementRepo] Failed to delete announcement: {e}")
            raise RepositoryException("Failed to delete announcement.")
