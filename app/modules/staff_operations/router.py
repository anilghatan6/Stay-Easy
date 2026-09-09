import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query

from app.middlewares.auth_middlewares import CurrentStaff
from app.modules.staff_operations.dependencies import get_staff_operations_service
from app.modules.staff_operations.schemas import (
    ActivityLogResponse,
    CheckInResponse,
    CheckOutResponse,
    EnumResponse,
    FrontDeskBookingResponse,
    FrontDeskSummaryResponse,
    StaffBookingDetailResponse,
    ModifyBookingResponse,
    ModifyBookingRequest,
    StaffCreateWalkinBookingRequest,
    StaffCreateWalkinBookingResponse,
    StaffCancelBookingRequest,
    StaffCancelBookingResponse,
)
from app.modules.staff_operations.service import StaffOperationsService
from app.modules.booking.models.booking_model import (
    MasterBookingStatus,
    PaymentGateway,
    PaymentStatus,
    PaymentMethod,
    BookingType,
)
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


@router.post(
    "/create-walkin-booking",
    status_code=201,
)
async def create_walkin_booking(
    payload: StaffCreateWalkinBookingRequest,
    staff: CurrentStaff,
    staff_ops_service: Annotated[StaffOperationsService, Depends(get_staff_operations_service)],
):
    result = await staff_ops_service.create_walkin_booking(
        staff_user=staff,
        payload=payload,
    )
    return StandardResponse(data=StaffCreateWalkinBookingResponse(**result))


@router.post("/cancel-booking/{ref_number}")
async def cancel_booking(
    ref_number: str,
    payload: StaffCancelBookingRequest,
    staff: CurrentStaff,
    staff_ops_service: Annotated[StaffOperationsService, Depends(get_staff_operations_service)],
):
    result = await staff_ops_service.cancel_booking(
        ref_number=ref_number,
        staff_user=staff,
        reason=payload.reason,
    )
    return StandardResponse(data=StaffCancelBookingResponse(**result))


# ─────────────────────────── Enum Endpoints ─────────────────────────


@router.get(
    "/enums/booking-statuses",
    response_model=StandardResponse[List[EnumResponse]],
    description="Get all available booking status options",
)
async def get_booking_statuses(
    staff: CurrentStaff,

):
    data = [
        EnumResponse(value=s.value, label=s.value.replace("_", " ").title())
        for s in MasterBookingStatus
    ]
    return StandardResponse(data=data)


@router.get(
    "/enums/payment-gateways",
    response_model=StandardResponse[List[EnumResponse]],
    description="Get all available payment gateway options",
)
async def get_payment_gateways(
    staff: CurrentStaff,

):
    data = [
        EnumResponse(value=g.value, label=g.value.replace("_", " ").title())
        for g in PaymentGateway
    ]
    return StandardResponse(data=data)


@router.get(
    "/enums/payment-statuses",
    response_model=StandardResponse[List[EnumResponse]],
    description="Get all available payment status options",
)
async def get_payment_statuses(
    staff: CurrentStaff,

):
    data = [
        EnumResponse(value=s.value, label=s.value.replace("_", " ").title())
        for s in PaymentStatus
    ]
    return StandardResponse(data=data)


@router.get(
    "/enums/payment-methods",
    response_model=StandardResponse[List[EnumResponse]],
    description="Get all available payment method options",
)
async def get_payment_methods(
    staff: CurrentStaff,

):
    data = [
        EnumResponse(value=m.value, label=m.value.replace("_", " ").title())
        for m in PaymentMethod
    ]
    return StandardResponse(data=data)


@router.get(
    "/enums/booking-types",
    response_model=StandardResponse[List[EnumResponse]],
    description="Get all available booking type options",
)
async def get_booking_types(
    staff: CurrentStaff,

):
    data = [
        EnumResponse(value=t.value, label=t.value.replace("_", " ").title())
        for t in BookingType
    ]
    return StandardResponse(data=data)


# ─────────────────────────── Activity Log ─────────────────────────


@router.get(
    "/properties/{property_id}/activities/booking",
    response_model=StandardResponse[List[ActivityLogResponse]],
    description="Get booking & front desk activities (check-in, check-out, walk-in, modify, cancel, room status)",
)
async def get_booking_activities(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    skip: int = Query(default=0, ge=0, description="Number of activities to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max activities to return"),
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    logs, total_count = await staff_ops_service.get_booking_activities(
        property_id=property_id,
        staff_user=staff,
        skip=skip,
        limit=limit,
    )
    has_more = skip + len(logs) < total_count
    return StandardResponse(
        data=[ActivityLogResponse.model_validate(log) for log in logs],
        meta={
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        },
    )


@router.get(
    "/properties/{property_id}/activities/housekeeping",
    response_model=StandardResponse[List[ActivityLogResponse]],
    description="Get housekeeping activities (task created, completed, status update, cleaning submitted, reviewed)",
)
async def get_housekeeping_activities(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    skip: int = Query(default=0, ge=0, description="Number of activities to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max activities to return"),
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    logs, total_count = await staff_ops_service.get_housekeeping_activities(
        property_id=property_id,
        staff_user=staff,
        skip=skip,
        limit=limit,
    )
    has_more = skip + len(logs) < total_count
    return StandardResponse(
        data=[ActivityLogResponse.model_validate(log) for log in logs],
        meta={
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        },
    )


# ─────────────────────────── Today's Arrivals / Departures ─────────────────────────


@router.get(
    "/properties/{property_id}/today/arrivals",
    response_model=StandardResponse[List[FrontDeskBookingResponse]],
    description="Get all guests arriving today (check-in date is today)",
)
async def get_todays_arrivals(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    result = await staff_ops_service.get_todays_arrivals(
        property_id=property_id,
        staff_user=staff,
    )
    return StandardResponse(data=[FrontDeskBookingResponse(**b) for b in result])


@router.get(
    "/properties/{property_id}/today/departures",
    response_model=StandardResponse[List[FrontDeskBookingResponse]],
    description="Get all guests departing today (check-out date is today)",
)
async def get_todays_departures(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    result = await staff_ops_service.get_todays_departures(
        property_id=property_id,
        staff_user=staff,
    )
    return StandardResponse(data=[FrontDeskBookingResponse(**b) for b in result])


@router.get(
    "/properties/{property_id}/front-desk-summary",
    response_model=StandardResponse[FrontDeskSummaryResponse],
    description="Get front desk summary: today's arrivals, departures, check-ins, check-outs, room counts",
)
async def get_front_desk_summary(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    result = await staff_ops_service.get_front_desk_summary(
        property_id=property_id,
        staff_user=staff,
    )
    return StandardResponse(data=FrontDeskSummaryResponse(**result))
