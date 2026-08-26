import uuid
from typing import List

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, status

from app.modules.housekeeping_mobile.auth import CurrentHousekeepingStaff
from app.modules.housekeeping_mobile.schemas.maintenance_schemas import MaintenanceReportResponse
from app.modules.housekeeping_mobile.services.maintenance_service import MaintenanceService
from app.modules.housekeeping_mobile.dependencies import get_maintenance_service
from app.modules.housekeeping_mobile.models.maintenance_report_model import MaintenanceCategory
from app.modules.house_keeping.models.task_model import TaskPriority
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(
    prefix="/properties/{property_id}/housekeeping/maintenance",
    tags=["housekeeping-mobile-maintenance"],
)


@router.post(
    "",
    response_model=StandardResponse[MaintenanceReportResponse],
    status_code=status.HTTP_201_CREATED,
    description="Submit a maintenance report for a room issue",
)
async def create_maintenance_report(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    room_id: uuid.UUID = Form(...),
    category: MaintenanceCategory = Form(...),
    priority: TaskPriority = Form(TaskPriority.MEDIUM),
    description: str = Form(..., min_length=10, max_length=2000),
    files: List[UploadFile] = File(None, max_length=5),
    maintenance_service: MaintenanceService = Depends(get_maintenance_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(maintenance_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": None, "message": "Staff profile not found"}

    result = await maintenance_service.create_report(
        staff_id=staff.id,
        property_id=property_id,
        room_id=room_id,
        category=category,
        priority=priority,
        description=description,
        files=files,
    )
    return {"success": True, "data": result}


@router.get(
    "",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get maintenance reports submitted by the logged-in housekeeping staff",
)
async def get_my_reports(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    maintenance_service: MaintenanceService = Depends(get_maintenance_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(maintenance_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": [], "message": "Staff profile not found"}

    result, total = await maintenance_service.get_my_reports(staff.id, property_id, skip, limit)
    has_more = (skip + len(result)) < total
    return {
        "success": True,
        "data": result,
        "meta": {"total": total, "skip": skip, "limit": limit, "has_more": has_more},
    }
