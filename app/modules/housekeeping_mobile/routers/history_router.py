import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.modules.housekeeping_mobile.auth import CurrentHousekeepingStaff
from app.modules.housekeeping_mobile.schemas.history_schemas import WorkHistoryResponse, WorkHistoryStatsResponse
from app.modules.housekeeping_mobile.services.history_service import HistoryService
from app.modules.housekeeping_mobile.dependencies import get_history_service
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(
    prefix="/properties/{property_id}/housekeeping/history",
    tags=["housekeeping-mobile-history"],
)


@router.get(
    "",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get work history for the logged-in housekeeping staff (tasks and maintenance reports)",
)
async def get_work_history(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    from_date: Optional[date] = Query(None, description="Filter from date"),
    to_date: Optional[date] = Query(None, description="Filter to date"),
    history_service: HistoryService = Depends(get_history_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(history_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": [], "message": "Staff profile not found"}

    result, total = await history_service.get_work_history(
        staff.id, property_id, skip, limit, from_date, to_date
    )
    has_more = (skip + len(result)) < total
    return {
        "success": True,
        "data": result,
        "meta": {"total": total, "skip": skip, "limit": limit, "has_more": has_more},
    }


@router.get(
    "/stats",
    response_model=StandardResponse[WorkHistoryStatsResponse],
    status_code=status.HTTP_200_OK,
    description="Get work statistics for the logged-in housekeeping staff",
)
async def get_work_stats(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    history_service: HistoryService = Depends(get_history_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(history_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": None, "message": "Staff profile not found"}

    result = await history_service.get_work_stats(staff.id, property_id)
    return {"success": True, "data": result}
