import uuid
from datetime import date, datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, func, union_all
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.house_keeping.models.task_model import (
    HousekeepingTask,
    TaskStatus,
)
from app.modules.housekeeping_mobile.models.maintenance_report_model import MaintenanceReport
from app.modules.pms.models.rooms_model import Rooms
from app.modules.staff_mgmt.models.staffs_model import Staff
from app.modules.auth.models import User
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class HistoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_work_history(
        self,
        staff_id: uuid.UUID,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> tuple[List[dict], int]:
        logger.info(f"[HistoryRepository] Fetching work history for staff {staff_id}")
        try:
            # Completed tasks
            task_query = (
                select(
                    HousekeepingTask.id,
                    HousekeepingTask.created_at,
                    HousekeepingTask.completed_at,
                    HousekeepingTask.status,
                    HousekeepingTask.notes,
                    HousekeepingTask.task_type,
                    HousekeepingTask.priority,
                    Rooms.room_name,
                    Rooms.floor_number,
                    User.full_name.label("assigned_by_name"),
                )
                .join(Rooms, HousekeepingTask.room_id == Rooms.id)
                .outerjoin(User, HousekeepingTask.assigned_by_id == User.id)
                .where(
                    HousekeepingTask.assigned_staff_id == staff_id,
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.COMPLETED,
                )
            )

            # Maintenance reports
            report_query = (
                select(
                    MaintenanceReport.id,
                    MaintenanceReport.created_at,
                    MaintenanceReport.resolved_at,
                    MaintenanceReport.status,
                    MaintenanceReport.description.label("notes"),
                    func.cast(None, HousekeepingTask.task_type).label("task_type"),
                    MaintenanceReport.priority,
                    Rooms.room_name,
                    Rooms.floor_number,
                    func.cast(None, User.full_name).label("assigned_by_name"),
                )
                .join(Rooms, MaintenanceReport.room_id == Rooms.id)
                .outerjoin(Staff, MaintenanceReport.staff_id == Staff.id)
                .outerjoin(User, Staff.email == User.email)
                .where(
                    MaintenanceReport.staff_id == staff_id,
                    MaintenanceReport.property_id == property_id,
                )
            )

            if from_date:
                task_query = task_query.where(
                    HousekeepingTask.completed_at >= datetime.combine(from_date, datetime.min.time())
                )
                report_query = report_query.where(
                    MaintenanceReport.created_at >= datetime.combine(from_date, datetime.min.time())
                )
            if to_date:
                end_of_day = datetime.combine(to_date + timedelta(days=1), datetime.min.time())
                task_query = task_query.where(HousekeepingTask.completed_at < end_of_day)
                report_query = report_query.where(MaintenanceReport.created_at < end_of_day)

            # Execute and merge
            task_result = await self.db.execute(task_query)
            task_rows = task_result.all()

            report_result = await self.db.execute(report_query)
            report_rows = report_result.all()

            history = []
            for row in task_rows:
                duration = None
                if row.completed_at and row.created_at:
                    duration = int((row.completed_at - row.created_at).total_seconds() / 60)
                history.append({
                    "id": row.id,
                    "activity_type": "TASK",
                    "room_name": row.room_name,
                    "room_floor": row.floor_number,
                    "task_type": row.task_type,
                    "priority": row.priority,
                    "maintenance_category": None,
                    "status": row.status,
                    "assigned_by_name": row.assigned_by_name,
                    "completed_at": row.completed_at,
                    "duration_minutes": duration,
                    "notes": row.notes,
                    "created_at": row.created_at,
                })

            for row in report_rows:
                history.append({
                    "id": row.id,
                    "activity_type": "MAINTENANCE_REPORT",
                    "room_name": row.room_name,
                    "room_floor": row.floor_number,
                    "task_type": None,
                    "priority": row.priority,
                    "maintenance_category": None,
                    "status": row.status,
                    "assigned_by_name": row.assigned_by_name,
                    "completed_at": row.resolved_at,
                    "duration_minutes": None,
                    "notes": row.notes,
                    "created_at": row.created_at,
                })

            # Sort by created_at desc
            history.sort(key=lambda x: x["created_at"], reverse=True)
            total = len(history)
            paginated = history[skip:skip + limit]

            return paginated, total

        except SQLAlchemyError as e:
            logger.error(f"[HistoryRepository] Failed to fetch work history: {e}")
            raise RepositoryException("Could not fetch work history.") from e

    async def get_work_stats(
        self, staff_id: uuid.UUID, property_id: uuid.UUID
    ) -> dict:
        logger.info(f"[HistoryRepository] Fetching work stats for staff {staff_id}")
        try:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            month_start = today.replace(day=1)

            # Total completed tasks
            total_stmt = (
                select(func.count())
                .select_from(HousekeepingTask)
                .where(
                    HousekeepingTask.assigned_staff_id == staff_id,
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.COMPLETED,
                )
            )
            total_result = await self.db.execute(total_stmt)
            total_tasks = total_result.scalar() or 0

            # Total maintenance reports
            report_stmt = (
                select(func.count())
                .select_from(MaintenanceReport)
                .where(
                    MaintenanceReport.staff_id == staff_id,
                    MaintenanceReport.property_id == property_id,
                )
            )
            report_result = await self.db.execute(report_stmt)
            total_reports = report_result.scalar() or 0

            # Total duration
            duration_stmt = (
                select(
                    func.sum(
                        func.extract("epoch", HousekeepingTask.completed_at - HousekeepingTask.created_at) / 60
                    )
                )
                .where(
                    HousekeepingTask.assigned_staff_id == staff_id,
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.COMPLETED,
                    HousekeepingTask.completed_at.isnot(None),
                )
            )
            duration_result = await self.db.execute(duration_stmt)
            total_duration = int(duration_result.scalar() or 0)

            # Today's completions
            today_stmt = (
                select(func.count())
                .select_from(HousekeepingTask)
                .where(
                    HousekeepingTask.assigned_staff_id == staff_id,
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.COMPLETED,
                    HousekeepingTask.completed_at >= datetime.combine(today, datetime.min.time()),
                    HousekeepingTask.completed_at < datetime.combine(today + timedelta(days=1), datetime.min.time()),
                )
            )
            today_result = await self.db.execute(today_stmt)
            today_count = today_result.scalar() or 0

            # This week's completions
            week_stmt = (
                select(func.count())
                .select_from(HousekeepingTask)
                .where(
                    HousekeepingTask.assigned_staff_id == staff_id,
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.COMPLETED,
                    HousekeepingTask.completed_at >= datetime.combine(week_start, datetime.min.time()),
                )
            )
            week_result = await self.db.execute(week_stmt)
            week_count = week_result.scalar() or 0

            # This month's completions
            month_stmt = (
                select(func.count())
                .select_from(HousekeepingTask)
                .where(
                    HousekeepingTask.assigned_staff_id == staff_id,
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.COMPLETED,
                    HousekeepingTask.completed_at >= datetime.combine(month_start, datetime.min.time()),
                )
            )
            month_result = await self.db.execute(month_stmt)
            month_count = month_result.scalar() or 0

            return {
                "total_tasks_completed": total_tasks,
                "total_maintenance_reports": total_reports,
                "total_duration_minutes": total_duration,
                "tasks_completed_today": today_count,
                "tasks_completed_this_week": week_count,
                "tasks_completed_this_month": month_count,
            }

        except SQLAlchemyError as e:
            logger.error(f"[HistoryRepository] Failed to fetch work stats: {e}")
            raise RepositoryException("Could not fetch work stats.") from e
