import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.modules.housekeeping_mobile.auth import CurrentHousekeepingStaff
from app.modules.housekeeping_mobile.schemas.task_schemas import MyTaskResponse, TaskStatusUpdateRequest
from app.modules.housekeeping_mobile.services.task_service import MobileTaskService
from app.modules.housekeeping_mobile.dependencies import get_mobile_task_service
from app.modules.house_keeping.models.task_model import TaskStatus
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(
    prefix="/properties/{property_id}/housekeeping/tasks",
    tags=["housekeeping-mobile-tasks"],
)


@router.get(
    "",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get tasks assigned to the logged-in housekeeping staff",
)
async def get_my_tasks(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    task_status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    task_service: MobileTaskService = Depends(get_mobile_task_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(task_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": [], "message": "Staff profile not found"}

    task_list, total = await task_service.get_my_tasks(
        staff.id, property_id, skip, limit, task_status
    )
    has_more = (skip + len(task_list)) < total
    return {
        "success": True,
        "data": task_list,
        "meta": {"total": total, "skip": skip, "limit": limit, "has_more": has_more},
    }


@router.get(
    "/{task_id}",
    response_model=StandardResponse[MyTaskResponse],
    status_code=status.HTTP_200_OK,
    description="Get a specific task assigned to the logged-in staff",
)
async def get_my_task(
    property_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    task_service: MobileTaskService = Depends(get_mobile_task_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(task_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": None, "message": "Staff profile not found"}

    result = await task_service.get_task_by_id(staff.id, property_id, task_id)
    return {"success": True, "data": result}


@router.patch(
    "/{task_id}/status",
    response_model=StandardResponse[MyTaskResponse],
    status_code=status.HTTP_200_OK,
    description="Update the status of a task (start, complete, cancel)",
)
async def update_task_status(
    property_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: TaskStatusUpdateRequest,
    current_user: CurrentHousekeepingStaff,
    task_service: MobileTaskService = Depends(get_mobile_task_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(task_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": None, "message": "Staff profile not found"}

    result = await task_service.update_task_status(
        staff.id, property_id, task_id, payload.status
    )
    return {"success": True, "data": result}
