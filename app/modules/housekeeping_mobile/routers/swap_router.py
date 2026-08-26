import uuid

from fastapi import APIRouter, Depends, Query, status

from app.modules.housekeeping_mobile.auth import CurrentHousekeepingStaff
from app.modules.housekeeping_mobile.schemas.schedule_schemas import ShiftSwapRequestCreate, ShiftSwapResponse
from app.modules.housekeeping_mobile.services.schedule_service import ScheduleService
from app.modules.housekeeping_mobile.dependencies import get_schedule_service
from app.modules.housekeeping_mobile.repositories.schedule_repository import ScheduleRepository
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(
    prefix="/properties/{property_id}/housekeeping/swap",
    tags=["housekeeping-mobile-swap"],
)


@router.post(
    "",
    response_model=StandardResponse[ShiftSwapResponse],
    status_code=status.HTTP_201_CREATED,
    description="Request a shift swap with another staff member",
)
async def create_swap_request(
    property_id: uuid.UUID,
    payload: ShiftSwapRequestCreate,
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

    # Verify target staff exists and is housekeeping
    target_staff = await task_repo.get_staff_by_user_id(payload.target_staff_id)
    if not target_staff:
        return {"success": False, "data": None, "message": "Target staff not found"}

    swap_data = {
        "property_id": property_id,
        "requester_staff_id": staff.id,
        "requester_shift": staff.shift,
        "target_staff_id": payload.target_staff_id,
        "target_shift": payload.target_shift,
        "reason": payload.reason,
    }

    swap = await schedule_repo.create_swap_request(swap_data)
    await schedule_service.db.commit()
    await schedule_service.db.refresh(swap)

    result = ShiftSwapResponse(
        id=swap.id,
        requester_staff_id=swap.requester_staff_id,
        requester_staff_name=staff.full_name,
        target_staff_id=swap.target_staff_id,
        target_staff_name=target_staff.full_name,
        requester_shift=swap.requester_shift,
        target_shift=swap.target_shift,
        reason=swap.reason,
        status=swap.status,
        reviewed_at=swap.reviewed_at,
        created_at=swap.created_at,
    )
    return {"success": True, "data": result}


@router.get(
    "",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get swap requests involving the logged-in housekeeping staff",
)
async def get_my_swap_requests(
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

    schedule_repo = ScheduleRepository(schedule_service.db)
    swaps, total = await schedule_repo.get_swap_requests_for_staff(staff.id, skip, limit)

    result = []
    for s in swaps:
        result.append({
            "id": s.id,
            "requester_staff_id": s.requester_staff_id,
            "requester_staff_name": s.requester_staff.full_name if s.requester_staff else "Unknown",
            "target_staff_id": s.target_staff_id,
            "target_staff_name": s.target_staff.full_name if s.target_staff else "Unknown",
            "requester_shift": s.requester_shift,
            "target_shift": s.target_shift,
            "reason": s.reason,
            "status": s.status,
            "reviewed_at": s.reviewed_at,
            "created_at": s.created_at,
        })

    has_more = (skip + len(result)) < total
    return {
        "success": True,
        "data": result,
        "meta": {"total": total, "skip": skip, "limit": limit, "has_more": has_more},
    }


@router.delete(
    "/{swap_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    description="Cancel a pending swap request",
)
async def cancel_swap_request(
    property_id: uuid.UUID,
    swap_id: uuid.UUID,
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
    swap = await schedule_repo.cancel_swap_request(swap_id, staff.id)
    if not swap:
        return {"success": False, "data": None, "message": "Swap request not found or already processed"}
    await schedule_service.db.commit()
    return {"success": True, "data": "Swap request cancelled successfully"}
