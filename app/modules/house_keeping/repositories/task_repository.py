import uuid
from typing import Optional, List, Sequence

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.house_keeping.models.task_model import (
    HousekeepingTask,
    TaskType,
    TaskStatus,
    TaskPriority,
)
from app.modules.pms.models.rooms_model import Rooms, RoomStatus
from app.modules.pms.models.properties_model import Property
from app.modules.staff_mgmt.models.staffs_model import Staff, StaffProperty
from app.modules.auth.models import User
from app.utils.exceptions import (
    RepositoryException,
    RoomNotFoundException,
    StaffNotFound,
    PropertyNotFoundException,
)
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── CREATE ──────────────────────────────────────

    async def create_task(self, task_data: dict) -> HousekeepingTask:
        logger.info("[TaskRepository] Creating housekeeping task")
        try:
            task = HousekeepingTask(id=uuid.uuid4(), **task_data)
            self.db.add(task)
            await self.db.flush()
            await self.db.refresh(task)
            return task
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[TaskRepository] Failed to create task: {e}")
            raise RepositoryException("Could not create task. Please try again.") from e

    async def bulk_create_tasks(self, tasks_data: list[dict]) -> list[HousekeepingTask]:
        logger.info(f"[TaskRepository] Bulk creating {len(tasks_data)} tasks")
        try:
            tasks = [HousekeepingTask(id=uuid.uuid4(), **data) for data in tasks_data]
            self.db.add_all(tasks)
            await self.db.flush()
            for task in tasks:
                await self.db.refresh(task)
            return tasks
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[TaskRepository] Failed to bulk create tasks: {e}")
            raise RepositoryException("Could not create tasks. Please try again.") from e

    # ─── READ ──────────────────────────────────────

    async def get_task_by_id(self, task_id: uuid.UUID) -> Optional[HousekeepingTask]:
        logger.info(f"[TaskRepository] Fetching task by id: {task_id}")
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
            logger.error(f"[TaskRepository] Failed to fetch task {task_id}: {e}")
            raise RepositoryException("Could not fetch task details.") from e

    async def list_tasks_with_details(
        self,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
        search: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
    ) -> tuple[List[HousekeepingTask], int]:
        logger.info(f"[TaskRepository] Listing tasks for property {property_id}")
        try:
            base_filter = HousekeepingTask.property_id == property_id

            stmt = (
                select(HousekeepingTask)
                .join(Rooms, HousekeepingTask.room_id == Rooms.id)
                .join(Staff, HousekeepingTask.assigned_staff_id == Staff.id)
                .outerjoin(User, HousekeepingTask.assigned_by_id == User.id)
                .where(base_filter)
                .options(
                    joinedload(HousekeepingTask.room),
                    joinedload(HousekeepingTask.assigned_staff),
                    joinedload(HousekeepingTask.assigned_by),
                )
            )

            count_stmt = (
                select(func.count())
                .select_from(HousekeepingTask)
                .join(Rooms, HousekeepingTask.room_id == Rooms.id)
                .where(base_filter)
            )

            if search:
                search_filter = func.lower(Rooms.room_name).contains(search.lower())
                stmt = stmt.where(search_filter)
                count_stmt = count_stmt.where(search_filter)

            if status is not None:
                stmt = stmt.where(HousekeepingTask.status == status)
                count_stmt = count_stmt.where(HousekeepingTask.status == status)

            if priority is not None:
                stmt = stmt.where(HousekeepingTask.priority == priority)
                count_stmt = count_stmt.where(HousekeepingTask.priority == priority)

            stmt = stmt.order_by(HousekeepingTask.created_at.desc()).offset(skip).limit(limit)

            result = await self.db.execute(stmt)
            tasks = list(result.unique().scalars().all())

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            logger.info(f"[TaskRepository] Found {len(tasks)} tasks for property {property_id}")
            return tasks, total

        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to list tasks: {e}")
            raise RepositoryException("Could not fetch tasks.") from e

    async def get_task_types(self) -> list[dict]:
        logger.info("[TaskRepository] Fetching task types")
        return [{"value": t.value, "label": t.value.replace("_", " ").title()} for t in TaskType]

    async def get_rooms_by_statuses(
        self, property_id: uuid.UUID, statuses: list[RoomStatus], skip: int = 0, limit: int = 50
    ) -> tuple[List[Rooms], int]:
        logger.info(f"[TaskRepository] Fetching rooms with statuses {[s.value for s in statuses]} for property {property_id}")
        try:
            stmt = (
                select(Rooms)
                .where(Rooms.property_id == property_id, Rooms.status.in_(statuses))
                .options(joinedload(Rooms.room_type), joinedload(Rooms.bed_type))
                .order_by(Rooms.room_name.asc())
                .offset(skip)
                .limit(limit)
            )

            count_stmt = (
                select(func.count())
                .select_from(Rooms)
                .where(Rooms.property_id == property_id, Rooms.status.in_(statuses))
            )

            result = await self.db.execute(stmt)
            rooms = list(result.unique().scalars().all())

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            return rooms, total

        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to fetch rooms by status: {e}")
            raise RepositoryException("Could not fetch rooms.") from e

    async def get_housekeeping_staff(
        self, property_id: uuid.UUID
    ) -> list[Staff]:
        logger.info(f"[TaskRepository] Fetching housekeeping staff for property {property_id}")
        try:
            stmt = (
                select(Staff)
                .join(StaffProperty, StaffProperty.staff_id == Staff.id)
                .where(
                    StaffProperty.property_id == property_id,
                    Staff.job_role == "HOUSEKEEPING",
                    Staff.status == "ACTIVE",
                )
                .options(selectinload(Staff.property_assignments))
                .order_by(Staff.full_name.asc())
            )
            result = await self.db.execute(stmt)
            staff_list = list(result.unique().scalars().all())
            logger.info(f"[TaskRepository] Found {len(staff_list)} housekeeping staff")
            return staff_list

        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to fetch housekeeping staff: {e}")
            raise RepositoryException("Could not fetch staff.") from e

    async def get_room_status_summary(self, property_id: uuid.UUID) -> dict:
        logger.info(f"[TaskRepository] Fetching room status summary for property {property_id}")
        try:
            stmt = (
                select(Rooms.status, func.count(Rooms.id))
                .where(Rooms.property_id == property_id)
                .group_by(Rooms.status)
            )
            result = await self.db.execute(stmt)
            rows = result.all()

            summary = {status.value: 0 for status in RoomStatus}
            for status_enum, count in rows:
                summary[status_enum] = count

            return {
                "total_rooms": sum(summary.values()),
                "available_rooms": summary.get("AVAILABLE", 0),
                "occupied_rooms": summary.get("OCCUPIED", 0),
                "dirty_rooms": summary.get("DIRTY", 0),
                "in_progress_rooms": summary.get("IN_PROGRESS", 0),
                "cleaning_rooms": summary.get("CLEANING", 0),
                "inspected_rooms": summary.get("INSPECTED", 0),
                "blocked_rooms": summary.get("BLOCKED", 0),
                "booked_rooms": summary.get("BOOKED", 0),
                "out_of_service_rooms": summary.get("OUT_OF_SERVICE", 0),
                "maintenance_rooms": summary.get("MAINTENANCE", 0),
            }

        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to fetch room status summary: {e}")
            raise RepositoryException("Could not fetch room status summary.") from e

    async def get_staff_work_summary(self, property_id: uuid.UUID) -> list[dict]:
        logger.info(f"[TaskRepository] Fetching staff work summary for property {property_id}")
        try:
            # Get total assigned per staff
            total_stmt = (
                select(
                    HousekeepingTask.assigned_staff_id,
                    func.count(HousekeepingTask.id).label("total_assigned"),
                )
                .where(HousekeepingTask.property_id == property_id)
                .group_by(HousekeepingTask.assigned_staff_id)
            )
            total_result = await self.db.execute(total_stmt)
            total_rows = {row.assigned_staff_id: row.total_assigned for row in total_result.all()}

            # Get completed per staff
            completed_stmt = (
                select(
                    HousekeepingTask.assigned_staff_id,
                    func.count(HousekeepingTask.id).label("completed"),
                )
                .where(
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.COMPLETED,
                )
                .group_by(HousekeepingTask.assigned_staff_id)
            )
            completed_result = await self.db.execute(completed_stmt)
            completed_rows = {row.assigned_staff_id: row.completed for row in completed_result.all()}

            # Get pending per staff
            pending_stmt = (
                select(
                    HousekeepingTask.assigned_staff_id,
                    func.count(HousekeepingTask.id).label("pending"),
                )
                .where(
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.PENDING,
                )
                .group_by(HousekeepingTask.assigned_staff_id)
            )
            pending_result = await self.db.execute(pending_stmt)
            pending_rows = {row.assigned_staff_id: row.pending for row in pending_result.all()}

            # Get in_progress per staff
            in_progress_stmt = (
                select(
                    HousekeepingTask.assigned_staff_id,
                    func.count(HousekeepingTask.id).label("in_progress"),
                )
                .where(
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.IN_PROGRESS,
                )
                .group_by(HousekeepingTask.assigned_staff_id)
            )
            in_progress_result = await self.db.execute(in_progress_stmt)
            in_progress_rows = {row.assigned_staff_id: row.in_progress for row in in_progress_result.all()}

            # Get cancelled per staff
            cancelled_stmt = (
                select(
                    HousekeepingTask.assigned_staff_id,
                    func.count(HousekeepingTask.id).label("cancelled"),
                )
                .where(
                    HousekeepingTask.property_id == property_id,
                    HousekeepingTask.status == TaskStatus.CANCELLED,
                )
                .group_by(HousekeepingTask.assigned_staff_id)
            )
            cancelled_result = await self.db.execute(cancelled_stmt)
            cancelled_rows = {row.assigned_staff_id: row.cancelled for row in cancelled_result.all()}

            # Get staff names
            staff = await self.get_housekeeping_staff(property_id)
            staff_map = {s.id: s.full_name for s in staff}

            # Merge counts
            all_staff_ids = set(total_rows.keys()) | set(completed_rows.keys())
            summary = []
            for staff_id in all_staff_ids:
                summary.append({
                    "staff_id": staff_id,
                    "staff_name": staff_map.get(staff_id, "Unknown"),
                    "total_assigned": total_rows.get(staff_id, 0),
                    "completed": completed_rows.get(staff_id, 0),
                    "pending": pending_rows.get(staff_id, 0),
                    "in_progress": in_progress_rows.get(staff_id, 0),
                    "cancelled": cancelled_rows.get(staff_id, 0),
                })

            # Add staff with zero tasks
            for s in staff:
                if s.id not in all_staff_ids:
                    summary.append({
                        "staff_id": s.id,
                        "staff_name": s.full_name,
                        "total_assigned": 0,
                        "completed": 0,
                        "pending": 0,
                        "in_progress": 0,
                        "cancelled": 0,
                    })

            # Sort by total_assigned descending
            summary.sort(key=lambda x: x["total_assigned"], reverse=True)
            return summary

        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to fetch staff work summary: {e}")
            raise RepositoryException("Could not fetch staff work summary.") from e

    # ─── UPDATE ──────────────────────────────────────

    async def update_task_fields(self, task_id: uuid.UUID, update_data: dict) -> Optional[HousekeepingTask]:
        logger.info(f"[TaskRepository] Updating task fields: {task_id}")
        try:
            task = await self.get_task_by_id(task_id)
            if task is None:
                return None

            for field, value in update_data.items():
                setattr(task, field, value)

            return task

        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to update task {task_id}: {e}")
            raise RepositoryException("Could not update task.") from e

    # ─── DELETE ──────────────────────────────────────

    async def delete_task(self, task_id: uuid.UUID) -> bool:
        logger.info(f"[TaskRepository] Deleting task: {task_id}")
        try:
            task = await self.get_task_by_id(task_id)
            if task is None:
                return False
            await self.db.delete(task)
            logger.info(f"[TaskRepository] Task deleted successfully: {task_id}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to delete task {task_id}: {e}")
            raise RepositoryException("Could not delete task.") from e

    # ─── VALIDATION ──────────────────────────────────

    async def verify_property_exists(
        self, property_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Property:
        logger.info(f"[TaskRepository] Verifying property {property_id} exists for tenant {tenant_id}")
        try:
            stmt = select(Property).where(
                Property.id == property_id,
                Property.tenant_id == tenant_id,
            )
            result = await self.db.execute(stmt)
            property_obj = result.scalar_one_or_none()
            if property_obj is None:
                raise PropertyNotFoundException("Property not found")
            return property_obj
        except PropertyNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to verify property: {e}")
            raise RepositoryException("Could not verify property.") from e

    async def verify_room_belongs_to_property(self, room_id: uuid.UUID, property_id: uuid.UUID) -> Rooms:
        try:
            stmt = select(Rooms).where(Rooms.id == room_id, Rooms.property_id == property_id)
            result = await self.db.execute(stmt)
            room = result.scalar_one_or_none()
            if room is None:
                raise RoomNotFoundException("Room not found for this property")
            return room
        except RoomNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to verify room: {e}")
            raise RepositoryException("Could not verify room.") from e

    async def verify_staff_assigned_to_property(self, staff_id: uuid.UUID, property_id: uuid.UUID) -> Staff:
        try:
            stmt = (
                select(Staff)
                .join(StaffProperty, StaffProperty.staff_id == Staff.id)
                .where(Staff.id == staff_id, StaffProperty.property_id == property_id)
            )
            result = await self.db.execute(stmt)
            staff = result.scalar_one_or_none()
            if staff is None:
                raise StaffNotFound("Staff not found for this property")
            return staff
        except StaffNotFound:
            raise
        except SQLAlchemyError as e:
            logger.error(f"[TaskRepository] Failed to verify staff: {e}")
            raise RepositoryException("Could not verify staff.") from e
