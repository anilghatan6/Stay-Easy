
import uuid
from typing import Optional

from app.modules.house_keeping.repositories.task_repository import TaskRepository
from app.modules.staff_mgmt.models.staffs_model import JobRole
from app.utils.exceptions import  RepositoryException,ServiceException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class TaskService:
    def __init__(self, task_repo: TaskRepository):
        self.task_repo = task_repo
    
    def _to_response_dict(self, task, room_name: str, staff_name: str) -> dict:
        return {
            "id": task.id,
            "property_id": task.property_id,
            "room_id": task.room_id,
            "room_name": room_name,
            "task_type": task.task_type,
            "priority": task.priority,
            "status": task.status,
            "assigned_staff_id": task.assigned_staff_id,
            "assigned_staff_name": staff_name,
            "due_time": task.due_time,
            "notes": task.notes,
            "completed_at": task.completed_at,
            "created_at": task.created_at,
        }

    async def create_task(
        self, property_id: uuid.UUID, assigned_by_id: uuid.UUID, payload
    ) -> dict:
        room = await self.task_repo.verify_room_belongs_to_property(payload.room_id, property_id)

        staff = await self.task_repo.verify_staff_assigned_to_property(payload.assigned_staff_id, property_id)

        if staff.job_role != JobRole.HOUSEKEEPING:
            raise ServiceException(user_message="Selected staff member is not a housekeeping staff", status_code=400)

        task_data = {
                "property_id": property_id,
                "room_id": payload.room_id,
                "task_type": payload.task_type,
                "priority": payload.priority,
                "assigned_staff_id": payload.assigned_staff_id,
                "assigned_by_id": assigned_by_id,
                "due_time": payload.due_time,
                "notes": payload.notes,
            }

        task = await self.task_repo.create_task(task_data)
        return self._to_response_dict(task, room.room_name, staff.full_name)   
