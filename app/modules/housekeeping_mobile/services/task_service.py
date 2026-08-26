import uuid
from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
from app.modules.house_keeping.models.task_model import TaskStatus
from app.utils.exceptions import ServiceException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class MobileTaskService:
    def __init__(self, db: AsyncSession, task_repo: MobileTaskRepository):
        self.db = db
        self.task_repo = task_repo

    def _to_response_dict(self, task) -> dict:
        return {
            "id": task.id,
            "property_id": task.property_id,
            "room_id": task.room_id,
            "room_name": task.room.room_name if task.room else "",
            "room_status": task.room.status if task.room else None,
            "floor_number": task.room.floor_number if task.room else None,
            "task_type": task.task_type,
            "priority": task.priority,
            "status": task.status,
            "assigned_by_name": task.assigned_by.full_name if task.assigned_by else None,
            "due_time": task.due_time,
            "notes": task.notes,
            "completed_at": task.completed_at,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    async def get_my_tasks(
        self,
        staff_id: uuid.UUID,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        status: Optional[TaskStatus] = None,
    ) -> tuple[list[dict], int]:
        tasks, total = await self.task_repo.get_my_tasks(
            staff_id, property_id, skip, limit, status
        )
        task_list = [self._to_response_dict(t) for t in tasks]
        return task_list, total

    async def get_task_by_id(
        self, staff_id: uuid.UUID, property_id: uuid.UUID, task_id: uuid.UUID
    ) -> dict:
        task = await self.task_repo.get_task_by_id(task_id)
        if task is None:
            raise ServiceException(user_message="Task not found", status_code=404)
        if task.assigned_staff_id != staff_id:
            raise ServiceException(user_message="Task not assigned to you", status_code=403)
        if task.property_id != property_id:
            raise ServiceException(user_message="Task not found for this property", status_code=404)
        return self._to_response_dict(task)

    async def update_task_status(
        self,
        staff_id: uuid.UUID,
        property_id: uuid.UUID,
        task_id: uuid.UUID,
        new_status: TaskStatus,
    ) -> dict:
        task = await self.task_repo.get_task_by_id(task_id)
        if task is None:
            raise ServiceException(user_message="Task not found", status_code=404)
        if task.assigned_staff_id != staff_id:
            raise ServiceException(user_message="Task not assigned to you", status_code=403)
        if task.property_id != property_id:
            raise ServiceException(user_message="Task not found for this property", status_code=404)

        # Validate status transitions
        allowed_transitions = {
            TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
            TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.CANCELLED],
            TaskStatus.AWAITING_INSPECTION: [TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED],
        }
        if new_status not in allowed_transitions.get(task.status, []):
            raise ServiceException(
                user_message=f"Cannot transition from {task.status} to {new_status}",
                status_code=400,
            )

        updated_task = await self.task_repo.update_task_status(task_id, new_status)
        await self.db.commit()
        await self.db.refresh(updated_task)
        return self._to_response_dict(updated_task)
