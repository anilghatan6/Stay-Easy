import uuid

from fastapi import APIRouter, Depends, Query, status

from app.modules.housekeeping_mobile.auth import CurrentHousekeepingStaff
from app.modules.housekeeping_mobile.schemas.schedule_schemas import LeaveRequestCreate, LeaveRequestResponse
from app.modules.housekeeping_mobile.services.schedule_service import ScheduleService
from app.modules.housekeeping_mobile.dependencies import get_schedule_service
from app.modules.housekeeping_mobile.repositories.schedule_repository import ScheduleRepository
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(
    prefix="/properties/{property_id}/housekeeping/leave",
    tags=["housekeeping-mobile-leave"],
)


@router.post(
    "",
    response_model=StandardResponse[LeaveRequestResponse],
    status_code=status.HTTP_201_CREATED,
    description="Submit a leave request",
)
async def create_leave_request(
    property_id: uuid.UUID,
    payload: LeaveRequestCreate,
    current_user: CurrentHousekeepingStaff,
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(schedule_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": None, "message": "Staff profile not found"}

    leave_data = {
        "property_id": property_id,
        "staff_id": staff.id,
        "leave_type": payload.leave_type,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "reason": payload.reason,
    }

    schedule_repo = ScheduleRepository(schedule_service.db)
    leave = await schedule_repo.create_leave_request(leave_data)
    await schedule_service.db.commit()
    await schedule_service.db.refresh(leave)

    result = LeaveRequestResponse(
        id=leave.id,
        staff_id=leave.staff_id,
        staff_name=staff.full_name,
        leave_type=leave.leave_type,
        start_date=leave.start_date,
        end_date=leave.end_date,
        reason=leave.reason,
        status=leave.status,
        reviewed_at=leave.reviewed_at,
        created_at=leave.created_at,
    )
    return {"success": True, "data": result}


@router.get(
    "",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get leave requests submitted by the logged-in housekeeping staff",
)
async def get_my_leave_requests(
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

    result, total = await schedule_service.get_leave_requests(staff.id, skip, limit)
    has_more = (skip + len(result)) < total
    return {
        "success": True,
        "data": result,
        "meta": {"total": total, "skip": skip, "limit": limit, "has_more": has_more},
    }


@router.delete(
    "/{leave_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    description="Cancel a pending leave request",
)
async def cancel_leave_request(
    property_id: uuid.UUID,
    leave_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    schedule_service: ScheduleService = Depends(get_schedule_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
    task_repo = MobileTaskRepository(schedule_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": None, "message": "Staff profile not found"}

    schedule_repo = ScheduleRepository(schedule_service.db)
    leave = await schedule_repo.cancel_leave_request(leave_id, staff.id)
    if not leave:
        return {"success": False, "data": None, "message": "Leave request not found or already processed"}
    await schedule_service.db.commit()
    return {"success": True, "data": "Leave request cancelled successfully"}
