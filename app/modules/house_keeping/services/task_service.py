import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.house_keeping.repositories.task_repository import TaskRepository
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.pms.models.rooms_model import RoomStatus
from app.modules.staff_mgmt.repositories.staffs_repository import StaffRepository
from app.modules.staff_mgmt.models.staffs_model import JobRole
from app.modules.staff_mgmt.schemas.staffs_schemas import StaffResponse
from app.utils.exceptions import (
    ServiceException,
    RepositoryException,
    PropertyNotFoundException,
    RoomNotFoundException,
    StaffNotFound,
)
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class TaskService:
    def __init__(
        self,
        db: AsyncSession,
        task_repo: TaskRepository,
        prop_repo: PropertyRepository,
        room_repo: RoomRepository,
        staff_repo: StaffRepository,
    ):
        self.db = db
        self.task_repo = task_repo
        self.prop_repo = prop_repo
        self.room_repo = room_repo
        self.staff_repo = staff_repo

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

    def _to_list_response_dict(self, task) -> dict:
        return {
            "id": task.id,
            "property_id": task.property_id,
            "room_id": task.room_id,
            "room_name": task.room.room_name if task.room else None,
            "room_status": task.room.status if task.room else None,
            "task_type": task.task_type,
            "priority": task.priority,
            "status": task.status,
            "assigned_staff_id": task.assigned_staff_id,
            "assigned_staff_name": task.assigned_staff.full_name if task.assigned_staff else None,
            "assigned_by_id": task.assigned_by_id,
            "assigned_by_name": task.assigned_by.full_name if task.assigned_by else None,
            "due_time": task.due_time,
            "notes": task.notes,
            "completed_at": task.completed_at,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    # ─── VALIDATION HELPERS ──────────────────────────

    async def _verify_property(self, tenant_id: uuid.UUID, property_id: uuid.UUID):
        try:
            await self.task_repo.verify_property_exists(property_id, tenant_id)
        except PropertyNotFoundException:
            raise
        except Exception:
            raise

    # ─── CREATE ──────────────────────────────────────

    async def create_task(
        self, tenant_id: uuid.UUID, property_id: uuid.UUID, assigned_by_id: uuid.UUID, payload
    ) -> dict:
        await self._verify_property(tenant_id, property_id)

        room = await self.task_repo.verify_room_belongs_to_property(payload.room_id, property_id)

        staff = await self.task_repo.verify_staff_assigned_to_property(
            payload.assigned_staff_id, property_id
        )

        if staff.job_role != JobRole.HOUSEKEEPING:
            raise ServiceException(
                user_message="Selected staff member is not a housekeeping staff",
                status_code=400,
            )

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

    async def bulk_create_tasks(
        self,
        tenant_id: uuid.UUID,
        property_id: uuid.UUID,
        assigned_by_id: uuid.UUID,
        tasks_items: list,
    ) -> dict:
        await self._verify_property(tenant_id, property_id)

        task_data_list = []
        for item in tasks_items:
            room = await self.task_repo.verify_room_belongs_to_property(item.room_id, property_id)

            staff = await self.task_repo.verify_staff_assigned_to_property(
                item.staff_id, property_id
            )

            if staff.job_role != JobRole.HOUSEKEEPING:
                raise ServiceException(
                    user_message=f"Staff member {staff.full_name} is not a housekeeping staff",
                    status_code=400,
                )

            task_data_list.append({
                "property_id": property_id,
                "room_id": item.room_id,
                "task_type": item.task_type,
                "priority": item.priority,
                "assigned_staff_id": item.staff_id,
                "assigned_by_id": assigned_by_id,
                "due_time": item.due_time,
                "notes": item.notes,
            })

        created_tasks = await self.task_repo.bulk_create_tasks(task_data_list)

        from app.modules.house_keeping.schemas.task_schema import TaskResponse

        task_responses = []
        for task in created_tasks:
            # Re-fetch with joins for response
            full_task = await self.task_repo.get_task_by_id(task.id)
            if full_task:
                task_responses.append(
                    TaskResponse(
                        id=full_task.id,
                        property_id=full_task.property_id,
                        room_id=full_task.room_id,
                        room_name=full_task.room.room_name if full_task.room else "",
                        task_type=full_task.task_type,
                        priority=full_task.priority,
                        status=full_task.status,
                        assigned_staff_id=full_task.assigned_staff_id,
                        assigned_staff_name=full_task.assigned_staff.full_name if full_task.assigned_staff else "",
                        due_time=full_task.due_time,
                        notes=full_task.notes,
                        completed_at=full_task.completed_at,
                        created_at=full_task.created_at,
                    )
                )

        return {"created_count": len(task_responses), "tasks": task_responses}

    # ─── READ ──────────────────────────────────────

    async def get_task_types(self) -> list[dict]:
        try:
            return await self.task_repo.get_task_types()
        except RepositoryException:
            raise
        except Exception as e:
            logger.error(f"[TaskService] Error fetching task types: {e}")
            raise ServiceException("Error fetching task types")

    async def get_task_by_id(
        self, tenant_id: uuid.UUID, property_id: uuid.UUID, task_id: uuid.UUID
    ) -> dict:
        await self._verify_property(tenant_id, property_id)

        task = await self.task_repo.get_task_by_id(task_id)
        if task is None:
            raise ServiceException(user_message="Task not found", status_code=404)

        if task.property_id != property_id:
            raise ServiceException(user_message="Task not found for this property", status_code=404)

        return self._to_response_dict(
            task,
            task.room.room_name if task.room else "",
            task.assigned_staff.full_name if task.assigned_staff else "",
        )

    async def list_tasks(
        self,
        tenant_id: uuid.UUID,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
        search: Optional[str] = None,
        status=None,
        priority=None,
    ) -> tuple[list[dict], int]:
        await self._verify_property(tenant_id, property_id)

        tasks, total = await self.task_repo.list_tasks_with_details(
            property_id=property_id,
            skip=skip,
            limit=limit,
            search=search,
            status=status,
            priority=priority,
        )

        task_list = [self._to_list_response_dict(task) for task in tasks]
        return task_list, total

    async def get_rooms_by_statuses(
        self,
        tenant_id: uuid.UUID,
        property_id: uuid.UUID,
        statuses: list[RoomStatus],
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        await self._verify_property(tenant_id, property_id)

        rooms, total = await self.task_repo.get_rooms_by_statuses(
            property_id=property_id,
            statuses=statuses,
            skip=skip,
            limit=limit,
        )

        room_list = [
            {
                "id": room.id,
                "room_name": room.room_name,
                "status": room.status,
                "floor_number": room.floor_number,
                "room_type": room.room_type.room_type_name if room.room_type else None,
                "bed_type": room.bed_type.bed_name if room.bed_type else None,
                "base_rate": str(room.base_rate) if room.base_rate else None,
            }
            for room in rooms
        ]
        return room_list, total

    async def get_housekeeping_staff(
        self, tenant_id: uuid.UUID, property_id: uuid.UUID
    ) -> list[StaffResponse]:
        await self._verify_property(tenant_id, property_id)

        staff_list = await self.task_repo.get_housekeeping_staff(property_id)
        return [StaffResponse.model_validate(s) for s in staff_list]

    async def get_room_status_summary(
        self, tenant_id: uuid.UUID, property_id: uuid.UUID
    ) -> dict:
        await self._verify_property(tenant_id, property_id)
        return await self.task_repo.get_room_status_summary(property_id)

    async def get_staff_work_summary(
        self, tenant_id: uuid.UUID, property_id: uuid.UUID
    ) -> list[dict]:
        await self._verify_property(tenant_id, property_id)
        return await self.task_repo.get_staff_work_summary(property_id)

    # ─── UPDATE ──────────────────────────────────────

    async def update_task(
        self,
        tenant_id: uuid.UUID,
        property_id: uuid.UUID,
        task_id: uuid.UUID,
        payload,
    ) -> dict:
        await self._verify_property(tenant_id, property_id)

        task = await self.task_repo.get_task_by_id(task_id)
        if task is None:
            raise ServiceException(user_message="Task not found", status_code=404)

        if task.property_id != property_id:
            raise ServiceException(user_message="Task not found for this property", status_code=404)

        update_data = payload.model_dump(exclude_unset=True)

        # If staff is being changed, verify the new staff
        if "assigned_staff_id" in update_data and update_data["assigned_staff_id"] != task.assigned_staff_id:
            new_staff = await self.task_repo.verify_staff_assigned_to_property(
                update_data["assigned_staff_id"], property_id
            )
            if new_staff.job_role != JobRole.HOUSEKEEPING:
                raise ServiceException(
                    user_message="Selected staff member is not a housekeeping staff",
                    status_code=400,
                )

        if update_data:
            await self.task_repo.update_task_fields(task_id, update_data)

        # Re-fetch for response
        updated_task = await self.task_repo.get_task_by_id(task_id)
        return self._to_response_dict(
            updated_task,
            updated_task.room.room_name if updated_task.room else "",
            updated_task.assigned_staff.full_name if updated_task.assigned_staff else "",
        )

    async def complete_task(
        self,
        tenant_id: uuid.UUID,
        property_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> dict:
        await self._verify_property(tenant_id, property_id)

        task = await self.task_repo.get_task_by_id(task_id)
        if task is None:
            raise ServiceException(user_message="Task not found", status_code=404)

        if task.property_id != property_id:
            raise ServiceException(user_message="Task not found for this property", status_code=404)

        await self.task_repo.update_task_fields(
            task_id,
            {
                "status": "COMPLETED",
                "completed_at": datetime.now(timezone.utc),
            },
        )

        completed_task = await self.task_repo.get_task_by_id(task_id)
        return self._to_response_dict(
            completed_task,
            completed_task.room.room_name if completed_task.room else "",
            completed_task.assigned_staff.full_name if completed_task.assigned_staff else "",
        )

    # ─── DELETE ──────────────────────────────────────

    async def delete_task(
        self,
        tenant_id: uuid.UUID,
        property_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> None:
        await self._verify_property(tenant_id, property_id)

        task = await self.task_repo.get_task_by_id(task_id)
        if task is None:
            raise ServiceException(user_message="Task not found", status_code=404)

        if task.property_id != property_id:
            raise ServiceException(user_message="Task not found for this property", status_code=404)

        deleted = await self.task_repo.delete_task(task_id)
        if not deleted:
            raise ServiceException(user_message="Task not found", status_code=404)
