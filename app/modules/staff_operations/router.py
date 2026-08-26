from typing import Annotated

from fastapi import APIRouter, Depends

from app.middlewares.auth_middlewares import CurrentStaff
from app.modules.staff_operations.dependencies import get_staff_operations_service
from app.modules.staff_operations.schemas import (
    CheckInResponse,
    CheckOutResponse,
    StaffBookingDetailResponse,
   
    ModifyBookingResponse,
    ModifyBookingRequest
)
from app.modules.staff_operations.service import StaffOperationsService
from app.utils.schemas import StandardResponse

router = APIRouter(
    prefix="/staff",
    tags=["staff-operations"],
)


@router.get("/bookings/{ref_number}")
async def get_booking_for_staff(
    ref_number: str,
    staff: CurrentStaff,
    staff_ops_service: Annotated[StaffOperationsService, Depends(get_staff_operations_service)],
):
    result = await staff_ops_service.get_booking_for_staff(
        ref_number=ref_number,
        staff_user=staff,
    )
    return StandardResponse(data=StaffBookingDetailResponse(**result))


@router.post("/check-in/{ref_number}")
async def check_in_guest(
    ref_number: str,
    staff: CurrentStaff,
    staff_ops_service: Annotated[StaffOperationsService, Depends(get_staff_operations_service)],
):
    result = await staff_ops_service.check_in_guest(
        ref_number=ref_number,
        staff_user=staff,
    )
    return StandardResponse(data=CheckInResponse(**result))


@router.post("/check-out/{ref_number}")
async def check_out_guest(
    ref_number: str,
    staff: CurrentStaff,
    staff_ops_service: Annotated[StaffOperationsService, Depends(get_staff_operations_service)],
):
    result = await staff_ops_service.check_out_guest(
        ref_number=ref_number,
        staff_user=staff,
    )
    return StandardResponse(data=CheckOutResponse(**result))

@router.patch("/{ref_number}/booking-modify")
async def modify_booking(
    ref_number: str,
    payload: ModifyBookingRequest,
    staff: CurrentStaff,
    staff_ops_service: Annotated[StaffOperationsService, Depends(get_staff_operations_service)],
):
    result = await staff_ops_service.modify_booking(
        ref_number=ref_number, staff_user=staff, payload=payload
    )
    return StandardResponse(data=ModifyBookingResponse(**result))
