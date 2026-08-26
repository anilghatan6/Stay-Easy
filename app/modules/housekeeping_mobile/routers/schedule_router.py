import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.modules.housekeeping_mobile.auth import CurrentHousekeepingStaff
from app.modules.housekeeping_mobile.schemas.schedule_schemas import ScheduleResponse
from app.modules.housekeeping_mobile.services.schedule_service import ScheduleService
from app.modules.housekeeping_mobile.dependencies import get_schedule_service
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(
    prefix="/properties/{property_id}/housekeeping/schedule",
    tags=["housekeeping-mobile-schedule"],
)


@router.get(
    "/today",
    response_model=StandardResponse[ScheduleResponse],
    status_code=status.HTTP_200_OK,
    description="Get today's schedule for the logged-in housekeeping staff",
)
async def get_today_schedule(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(schedule_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": None, "message": "Staff profile not found"}

    result = await schedule_service.get_today_schedule(staff.id, property_id)
    return {"success": True, "data": result}


@router.get(
    "/history",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get schedule history for the logged-in housekeeping staff",
)
async def get_schedule_history(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(schedule_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": [], "message": "Staff profile not found"}

    result, total = await schedule_service.get_schedule_history(staff.id, property_id, skip, limit)
    has_more = (skip + len(result)) < total
    return {
        "success": True,
        "data": result,
        "meta": {"total": total, "skip": skip, "limit": limit, "has_more": has_more},
    }


@router.get(
    "/weekly",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get weekly schedule for the logged-in housekeeping staff",
)
async def get_weekly_schedule(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    start_date: date = Query(None, description="Week start date (default: this Monday)"),
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(schedule_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": [], "message": "Staff profile not found"}

    result = await schedule_service.get_weekly_schedule(staff.id, property_id, start_date)
    return {"success": True, "data": result}


@router.get(
    "/monthly",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get monthly schedule for the logged-in housekeeping staff",
)
async def get_monthly_schedule(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(schedule_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": [], "message": "Staff profile not found"}

    result = await schedule_service.get_monthly_schedule(staff.id, property_id, year, month)
    return {"success": True, "data": result}
