import uuid
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.house_keeping.models.task_model import (
    HousekeepingTask,
    TaskStatus,
    TaskType,
    TaskPriority,
)
from app.modules.pms.models.rooms_model import Rooms
from app.modules.staff_mgmt.models.staffs_model import Staff, StaffProperty
from app.modules.auth.models import User
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class MobileTaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_my_tasks(
        self,
        staff_id: uuid.UUID,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        status: Optional[TaskStatus] = None,
    ) -> tuple[List[HousekeepingTask], int]:
        logger.info(f"[MobileTaskRepository] Fetching tasks for staff {staff_id}")
        try:
            base_filter = (
                HousekeepingTask.assigned_staff_id == staff_id,
                HousekeepingTask.property_id == property_id,
            )

            stmt = (
                select(HousekeepingTask)
                .join(Rooms, HousekeepingTask.room_id == Rooms.id)
                .outerjoin(User, HousekeepingTask.assigned_by_id == User.id)
                .where(*base_filter)
                .options(
                    joinedload(HousekeepingTask.room),
                    joinedload(HousekeepingTask.assigned_by),
                )
            )

            count_stmt = (
                select(func.count())
                .select_from(HousekeepingTask)
                .where(*base_filter)
            )

            if status is not None:
                stmt = stmt.where(HousekeepingTask.status == status)
                count_stmt = count_stmt.where(HousekeepingTask.status == status)

            stmt = stmt.order_by(HousekeepingTask.due_time.asc()).offset(skip).limit(limit)

            result = await self.db.execute(stmt)
            tasks = list(result.unique().scalars().all())

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            return tasks, total

        except SQLAlchemyError as e:
            logger.error(f"[MobileTaskRepository] Failed to fetch tasks: {e}")
            raise RepositoryException("Could not fetch tasks.") from e

    async def get_task_by_id(self, task_id: uuid.UUID) -> Optional[HousekeepingTask]:
        logger.info(f"[MobileTaskRepository] Fetching task {task_id}")
        try:
            stmt = (
                select(HousekeepingTask)
                .options(
                    joinedload(HousekeepingTask.room),
                    joinedload(HousekeepingTask.assigned_staff),
                    joinedload(HousekeepingTask.assigned_by),
                )
                .where(HousekeepingTask.id == task_id)
            )
            result = await self.db.execute(stmt)
            return result.unique().scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[MobileTaskRepository] Failed to fetch task: {e}")
            raise RepositoryException("Could not fetch task.") from e

    async def update_task_status(
        self, task_id: uuid.UUID, status: TaskStatus
    ) -> Optional[HousekeepingTask]:
        logger.info(f"[MobileTaskRepository] Updating task {task_id} status to {status}")
        try:
            task = await self.get_task_by_id(task_id)
            if task is None:
                return None
            task.status = status
            if status == TaskStatus.COMPLETED:
                from datetime import datetime, timezone
                task.completed_at = datetime.now(timezone.utc)
            return task
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[MobileTaskRepository] Failed to update task status: {e}")
            raise RepositoryException("Could not update task status.") from e

    async def get_staff_by_user_id(self, user_id: uuid.UUID) -> Optional[Staff]:
        logger.info(f"[MobileTaskRepository] Fetching staff by user_id {user_id}")
        try:
            stmt = (
                select(Staff)
                .join(User, func.lower(User.email) == func.lower(Staff.email))
                .where(User.id == user_id)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[MobileTaskRepository] Failed to fetch staff: {e}")
            raise RepositoryException("Could not fetch staff.") from e

    async def get_task_counts_for_date(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, target_date
    ) -> dict:
        logger.info(f"[MobileTaskRepository] Fetching task counts for staff {staff_id} on {target_date}")
        try:
            from datetime import datetime, timedelta
            start = datetime.combine(target_date, datetime.min.time())
            end = start + timedelta(days=1)

            assigned_stmt = (
                select(func.count())
                .select_from(HousekeepingTask)
                .where(
                    HousekeepingTask.assigned_staff_id == staff_id,
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.created_at >= start,
                    HousekeepingTask.created_at < end,
                )
            )
            completed_stmt = (
                select(func.count())
                .select_from(HousekeepingTask)
                .where(
                    HousekeepingTask.assigned_staff_id == staff_id,
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.COMPLETED,
                    HousekeepingTask.completed_at >= start,
                    HousekeepingTask.completed_at < end,
                )
            )

            assigned_result = await self.db.execute(assigned_stmt)
            completed_result = await self.db.execute(completed_stmt)

            return {
                "tasks_assigned_today": assigned_result.scalar() or 0,
                "tasks_completed_today": completed_result.scalar() or 0,
            }
        except SQLAlchemyError as e:
            logger.error(f"[MobileTaskRepository] Failed to fetch task counts: {e}")
            raise RepositoryException("Could not fetch task counts.") from e
