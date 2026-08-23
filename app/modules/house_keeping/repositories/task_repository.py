
import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.house_keeping.models.task_model import HousekeepingTask, TaskStatus
from app.modules.pms.models import Rooms
from app.modules.staff_mgmt.models import Staff
from app.utils.exceptions import RepositoryException,RoomNotFoundException,StaffNotFound
from app.utils.logging import LoggerFactory


logger = LoggerFactory.get_logger(__name__)


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(self, task_data: dict) -> HousekeepingTask:
        logger.info("[TaskRepository] Creating housekeeping task")
        try:
            task = HousekeepingTask(id=uuid.uuid4(), **task_data)
            self.db.add(task)
            await self.db.commit()
            await self.db.refresh(task)
            return task
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[TaskRepository] Failed to create task: {e}")
            raise RepositoryException("Could not create task. Please try again.") from e

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
            stmt = select(Staff).where(Staff.id == staff_id, Staff.property_id == property_id)
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
