
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





rooms_router = APIRouter(
    prefix="/properties/{property_id}/room-status",
    tags=["housekeeping-rooms"],
)


# ═══════════════════════════════════════════════════════
# ROOM-RELATED ROUTES (separate router, mounted separately)
# ═══════════════════════════════════════════════════════


# ─── ROOMS BY STATUS ─────────────────────────────────

@rooms_router.get(
    "",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get rooms filtered by room status, floor, room name, task status, and room type",
)
async def get_rooms_by_status(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    status: Optional[str] = Query(default=None, description="Room status (e.g., OCCUPIED)"),
    search: Optional[str] = Query(default=None, description="Search by room name (case-insensitive)"),
    floor_number: Optional[int] = Query(default=None, ge=0, description="Filter by floor number"),
    task_status: Optional[str] = Query(default=None, description="Comma-separated task statuses (e.g., PENDING,IN_PROGRESS)"),
    room_type: Optional[str] = Query(default=None, description="Filter by room type name"),
    skip: int = Query(0, ge=0, description="Number of rooms to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max rooms to return"),
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id

    parsed_room_status = None
    if status is not None:
        try:
            parsed_room_status = RoomStatus(status.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid room status: {status}. Allowed values: {', '.join(rs.value for rs in RoomStatus)}",
            )

    parsed_task_statuses = None
    if task_status is not None:
        parsed_task_statuses = []
        for s in task_status.split(","):
            s = s.strip().upper()
            if not s:
                continue
            try:
                parsed_task_statuses.append(TaskStatus(s))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid task status: {s}. Allowed values: {', '.join(ts.value for ts in TaskStatus)}",
                )
        if not parsed_task_statuses:
            parsed_task_statuses = None

    room_list, total = await task_service.get_rooms_by_status(
        tenant_id=tenant_id,
        property_id=property_id,
        status=parsed_room_status,
        search=search,
        floor_number=floor_number,
        task_status=parsed_task_statuses,
        room_type=room_type,
        skip=skip,
        limit=limit,
    )
    has_more = (skip + len(room_list)) < total
    return {
        "success": True,
        "data": room_list,
        "meta": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        },
    }


# ─── ROOM STATUS SUMMARY ─────────────────────────────

@rooms_router.get(
    "/summary",
    response_model=StandardResponse[RoomStatusSummaryResponse],
    status_code=status.HTTP_200_OK,
    description="Get room status counts for the property",
)
async def get_room_status_summary(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    task_service: TaskService = Depends(get_task_service),
):
    verify_tenant(current_user)
    tenant_id = current_user.tenant_id
    result = await task_service.get_room_status_summary(tenant_id, property_id)
    return {"success": True, "data": result}
