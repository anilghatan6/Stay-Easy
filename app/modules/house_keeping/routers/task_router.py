import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.house_keeping.schemas.task_schema import (
    CreateTaskRequest,
    UpdateTaskRequest,
    TaskResponse,
    TaskTypeEnumResponse,
    BulkAssignRequest,
    BulkAssignResponse,
    TaskListResponse,
    RoomStatusSummaryResponse,
    StaffWorkSummaryResponse,
)
from app.modules.house_keeping.models.task_model import TaskStatus, TaskPriority
from app.modules.pms.models.rooms_model import RoomStatus
from app.modules.house_keeping.services.task_service import TaskService
from app.middlewares.auth_middlewares import CurrentUser
from app.modules.house_keeping.dependencies import get_task_service
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(
    prefix="/properties/{property_id}/tasks",
    tags=["housekeeping-tasks"],
)


# ─── TASK TYPE OPTIONS ──────────────────────────────

@router.get(
    "/task-types",
    response_model=StandardResponse[List[TaskTypeEnumResponse]],
    status_code=status.HTTP_200_OK,
    description="Get all available task type options",
)
async def get_task_types(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    result = await task_service.get_task_types()
    return {"success": True, "data": result}


# ─── BULK ASSIGN ────────────────────────────────────

@router.post(
    "/bulk-assign",
    response_model=StandardResponse[BulkAssignResponse],
    status_code=status.HTTP_201_CREATED,
    description="Bulk assign housekeeping tasks",
)
async def bulk_assign_tasks(
    property_id: uuid.UUID,
    payload: BulkAssignRequest,
    current_user: CurrentUser,
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    result = await task_service.bulk_create_tasks(
        tenant_id, property_id, current_user.id, payload.tasks
    )
    return {"success": True, "data": result}


# ─── LIST TASKS (paginated, searchable, filterable) ─

@router.get(
    "",
    response_model=StandardResponse[List[TaskListResponse]],
    status_code=status.HTTP_200_OK,
    description="List housekeeping tasks with search and filters",
)
async def list_tasks(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0, description="Number of tasks to skip"),
    limit: int = Query(10, ge=1, le=50, description="Max tasks to return"),
    search: Optional[str] = Query(None, min_length=1, max_length=100, description="Search by room name"),
    task_status: Optional[TaskStatus] = Query(None, description="Filter by task status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id

    if task_status is not None and task_status not in TaskStatus:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Allowed values: {', '.join(s.value for s in TaskStatus)}",
        )
    if priority is not None and priority not in TaskPriority:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority. Allowed values: {', '.join(p.value for p in TaskPriority)}",
        )

    task_list, total = await task_service.list_tasks(
        tenant_id, property_id, skip, limit, search, task_status, priority
    )
    has_more = (skip + len(task_list)) < total
    return {
        "success": True,
        "data": task_list,
        "meta": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        },
    }


# ─── CREATE SINGLE TASK ─────────────────────────────

@router.post(
    "",
    response_model=StandardResponse[TaskResponse],
    status_code=status.HTTP_201_CREATED,
    description="Create a housekeeping task",
)
async def create_task(
    property_id: uuid.UUID,
    payload: CreateTaskRequest,
    current_user: CurrentUser,
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    result = await task_service.create_task(tenant_id, property_id, current_user.id, payload)
    return {"success": True, "data": result}


# ─── STAFF WORK SUMMARY ─────────────────────────────

@router.get(
    "/staff-work-summary",
    response_model=StandardResponse[List[StaffWorkSummaryResponse]],
    status_code=status.HTTP_200_OK,
    description="Get work summary for all housekeeping staff (total assigned, completed, pending, in_progress, cancelled)",
)
async def get_staff_work_summary(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    result = await task_service.get_staff_work_summary(tenant_id, property_id)
    return {"success": True, "data": result}


# @router.get(
#     "/housekeeping-staff",
#     response_model=StandardResponse[list],
#     status_code=status.HTTP_200_OK,
#     description="List housekeeping staff assigned to the property",
# )
# async def get_housekeeping_staff(
#     property_id: uuid.UUID,
#     current_user: CurrentUser,
#     task_service: TaskService = Depends(get_task_service),
# ):
#     verify_tenant(current_user)
#     tenant_id = current_user.tenant_id
#     result = await task_service.get_housekeeping_staff(tenant_id, property_id)
#     return {"success": True, "data": result}



# ─── GET SINGLE TASK ────────────────────────────────

@router.get(
    "/{task_id}",
    response_model=StandardResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    description="Get a housekeeping task by ID",
)
async def get_task(
    property_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: CurrentUser,
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    result = await task_service.get_task_by_id(tenant_id, property_id, task_id)
    return {"success": True, "data": result}


# ─── UPDATE TASK ─────────────────────────────────────

@router.patch(
    "/{task_id}",
    response_model=StandardResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    description="Update a housekeeping task",
)
async def update_task(
    property_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: UpdateTaskRequest,
    current_user: CurrentUser,
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    if "status" in update_data and update_data["status"] not in TaskStatus:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Allowed values: {', '.join(s.value for s in TaskStatus)}",
        )

    result = await task_service.update_task(tenant_id, property_id, task_id, payload)
    return {"success": True, "data": result}


# ─── COMPLETE TASK ───────────────────────────────────

@router.patch(
    "/{task_id}/complete",
    response_model=StandardResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    description="Mark a housekeeping task as completed",
)
async def complete_task(
    property_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: CurrentUser,
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    result = await task_service.complete_task(tenant_id, property_id, task_id)
    return {"success": True, "data": result}


# ─── DELETE TASK ─────────────────────────────────────

@router.delete(
    "/{task_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    description="Delete a housekeeping task",
)
async def delete_task(
    property_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: CurrentUser,
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    await task_service.delete_task(tenant_id, property_id, task_id)
    return {"success": True, "data": "Task deleted successfully"}

