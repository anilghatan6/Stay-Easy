import uuid
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.housekeeping_mobile.models.maintenance_report_model import MaintenanceReport
from app.modules.pms.models.rooms_model import Rooms
from app.modules.staff_mgmt.models.staffs_model import Staff
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class MaintenanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_report(self, data: dict) -> MaintenanceReport:
        logger.info("[MaintenanceRepository] Creating maintenance report")
        try:
            report = MaintenanceReport(id=uuid.uuid4(), **data)
            self.db.add(report)
            await self.db.flush()
            await self.db.refresh(report)
            return report
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[MaintenanceRepository] Failed to create report: {e}")
            raise RepositoryException("Could not create maintenance report.") from e

    async def get_reports_for_staff(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[List[MaintenanceReport], int]:
        logger.info(f"[MaintenanceRepository] Fetching reports for staff {staff_id}")
        try:
            stmt = (
                select(MaintenanceReport)
                .join(Rooms, MaintenanceReport.room_id == Rooms.id)
                .where(
                    MaintenanceReport.staff_id == staff_id,
                    MaintenanceReport.property_id == property_id,
                )
                .options(
                    joinedload(MaintenanceReport.room),
                    joinedload(MaintenanceReport.staff),
                )
                .order_by(MaintenanceReport.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

            count_stmt = (
                select(func.count())
                .select_from(MaintenanceReport)
                .where(
                    MaintenanceReport.staff_id == staff_id,
                    MaintenanceReport.property_id == property_id,
                )
            )

            result = await self.db.execute(stmt)
            reports = list(result.unique().scalars().all())

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            return reports, total
        except SQLAlchemyError as e:
            logger.error(f"[MaintenanceRepository] Failed to fetch reports: {e}")
            raise RepositoryException("Could not fetch maintenance reports.") from e

    async def get_report_by_id(self, report_id: uuid.UUID) -> Optional[MaintenanceReport]:
        logger.info(f"[MaintenanceRepository] Fetching report {report_id}")
        try:
            stmt = (
                select(MaintenanceReport)
                .options(
                    joinedload(MaintenanceReport.room),
                    joinedload(MaintenanceReport.staff),
                )
                .where(MaintenanceReport.id == report_id)
            )
            result = await self.db.execute(stmt)
            return result.unique().scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[MaintenanceRepository] Failed to fetch report: {e}")
            raise RepositoryException("Could not fetch report.") from e
