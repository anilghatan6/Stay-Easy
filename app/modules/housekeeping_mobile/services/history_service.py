import uuid
from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.housekeeping_mobile.repositories.history_repository import HistoryRepository
from app.utils.exceptions import ServiceException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class HistoryService:
    def __init__(self, db: AsyncSession, history_repo: HistoryRepository):
        self.db = db
        self.history_repo = history_repo

    async def get_work_history(
        self,
        staff_id: uuid.UUID,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> tuple[list[dict], int]:
        history, total = await self.history_repo.get_work_history(
            staff_id, property_id, skip, limit, from_date, to_date
        )
        return history, total

    async def get_work_stats(
        self, staff_id: uuid.UUID, property_id: uuid.UUID
    ) -> dict:
        return await self.history_repo.get_work_stats(staff_id, property_id)
