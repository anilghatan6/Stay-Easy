import uuid
from datetime import date, timedelta
from typing import Annotated, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException, File, UploadFile
from fastapi import status as http_status

from app.middlewares.auth_middlewares import CurrentStaff
from app.modules.staff_operations.dependencies import get_staff_operations_service
from app.modules.staff_operations.schemas import (
    ActivityLogResponse,
    CheckInPaymentRequest,
    CheckInResponse,
    CheckOutPaymentRequest,
    CheckOutResponse,
    CheckedInGuestItem,
    CitizenshipPhotosResponse,
    EnumResponse,
    FrontDeskBookingResponse,
    FrontDeskSummaryResponse,
    GuestBookingDetail,
    StaffBookingDetailResponse,
    ModifyBookingResponse,
    ModifyBookingRequest,
    StaffCreateWalkinBookingRequest,
    StaffCreateWalkinBookingResponse,
    StaffCancelBookingRequest,
    StaffCancelBookingResponse,
    RoomCalendarResponse,
)
from app.modules.staff_operations.service import StaffOperationsService
from app.modules.booking.models.booking_model import (
    MasterBookingStatus,
    PaymentGateway,
    PaymentStatus,
    PaymentMethod,
    BookingType,
)
from app.modules.pms.models.rooms_model import RoomStatus
from app.utils.schemas import StandardResponse

router = APIRouter(
    prefix="/staff",
    tags=["Front desk staff operations"],
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
    body: Optional[CheckInPaymentRequest] = None,
):
    payment_amount = body.amount if body else None
    payment_gateway = body.payment_gateway if body else None
    result = await staff_ops_service.check_in_guest(
        ref_number=ref_number,
        staff_user=staff,
        payment_amount=payment_amount,
        payment_gateway=payment_gateway,
    )
    return StandardResponse(data=CheckInResponse(**result))


@router.post(
    "/check-in/{ref_number}/citizenship-photos",
    response_model=StandardResponse[CitizenshipPhotosResponse],
    description="Upload or update citizenship front/back photos for a booking",
)
async def upload_citizenship_photos(
    ref_number: str,
    staff: CurrentStaff,
    staff_ops_service: Annotated[StaffOperationsService, Depends(get_staff_operations_service)],
    front: Optional[UploadFile] = File(None, description="Front side of citizenship document"),
    back: Optional[UploadFile] = File(None, description="Back side of citizenship document"),
):
    result = await staff_ops_service.upload_citizenship_photos(
        ref_number=ref_number,
        staff_user=staff,
        front_file=front,
        back_file=back,
    )
    return StandardResponse(data=CitizenshipPhotosResponse(**result["citizenship_photos"]))


@router.post("/check-out/{ref_number}")
async def check_out_guest(
    ref_number: str,
    staff: CurrentStaff,
    staff_ops_service: Annotated[StaffOperationsService, Depends(get_staff_operations_service)],
    body: Optional[CheckOutPaymentRequest] = None,
):
    payment_amount = body.amount if body else None
    payment_gateway = body.payment_gateway if body else None
    result = await staff_ops_service.check_out_guest(
        ref_number=ref_number,
        staff_user=staff,
        payment_amount=payment_amount,
        payment_gateway=payment_gateway,
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
    background_tasks: BackgroundTasks,
    staff_ops_service: Annotated[StaffOperationsService, Depends(get_staff_operations_service)],
):
    result = await staff_ops_service.cancel_booking(
        ref_number=ref_number,
        staff_user=staff,
        reason=payload.reason,
        background_tasks=background_tasks,
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


# ─────────────────────────── Expected Arrivals / Occupied Bookings ─────────────────────────


@router.get(
    "/properties/{property_id}/arrivals",
    response_model=StandardResponse[List[FrontDeskBookingResponse]],
    description="Get all bookings with check-in date today or in the future",
)
async def get_expected_arrivals(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    skip: int = Query(default=0, ge=0, description="Number of bookings to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max bookings to return"),
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    result, total_count = await staff_ops_service.get_expected_arrivals(
        property_id=property_id,
        staff_user=staff,
        skip=skip,
        limit=limit,
    )
    has_more = skip + len(result) < total_count
    return StandardResponse(
        data=[FrontDeskBookingResponse(**b) for b in result],
        meta={
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        },
    )


@router.get(
    "/properties/{property_id}/departures",
    response_model=StandardResponse[List[FrontDeskBookingResponse]],
    description="Get all occupied bookings with check-out date today or later",
)
async def get_occupied_bookings(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    skip: int = Query(default=0, ge=0, description="Number of bookings to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max bookings to return"),
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    result, total_count = await staff_ops_service.get_occupied_bookings(
        property_id=property_id,
        staff_user=staff,
        skip=skip,
        limit=limit,
    )
    has_more = skip + len(result) < total_count
    return StandardResponse(
        data=[FrontDeskBookingResponse(**b) for b in result],
        meta={
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        },
    )


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


# ─────────────────────────── Room Availability Calendar ─────────────────────────


@router.get(
    "/properties/{property_id}/room-calendar",
    response_model=StandardResponse[RoomCalendarResponse],
    description="Get room availability calendar showing each room's status for each day in a date range (max 1 month)",
)
async def get_room_calendar(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    start_date: Optional[date] = Query(None, description="Start date (defaults to today)"),
    end_date: Optional[date] = Query(None, description="End date (defaults to start_date + 6 days)"),
    floor_number: Optional[int] = Query(None, ge=0, le=1000, description="Filter by floor number"),
    room_status: Optional[RoomStatus] = Query(None, description="Filter by current room status"),
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    today = date.today()

    if start_date is None:
        start_date = today

    if end_date is None:
        end_date = start_date + timedelta(days=6)

    if end_date <= start_date:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date",
        )

    if (end_date - start_date).days > 30:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 31 days (1 month)",
        )

    result = await staff_ops_service.get_room_calendar(
        property_id=property_id,
        staff_user=staff,
        start_date=start_date,
        end_date=end_date,
        floor_number=floor_number,
        room_status=room_status,
    )
    return StandardResponse(data=RoomCalendarResponse(**result))


# ─────────────────────────── Checked-In Guests ─────────────────────────


@router.get(
    "/properties/{property_id}/booking-guests",
    description="Get all guests currently checked in at a property",
)
async def get_checked_in_guests(
    property_id: uuid.UUID,
    staff: CurrentStaff,
    skip: int = Query(default=0, ge=0, description="Number of guests to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max guests to return"),
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    result, total_count = await staff_ops_service.get_checked_in_guests_by_property(
        property_id=property_id,
        staff_user=staff,
        skip=skip,
        limit=limit,
    )
    has_more = skip + len(result) < total_count
    return StandardResponse(
        data=[CheckedInGuestItem(**g) for g in result],
        meta={
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        },
    )


# ─────────────────────────── Guest Bookings with Folio ─────────────────────────


@router.get(
    "/properties/{property_id}/bookings/{ref_number}/guest-folio",
    description="Get booking and folio details by reference number",
)
async def get_guest_booking_with_folio(
    property_id: uuid.UUID,
    ref_number: str,
    staff: CurrentStaff,
    staff_ops_service: StaffOperationsService = Depends(get_staff_operations_service),
):
    result = await staff_ops_service.get_guest_booking_with_folio(
        property_id=property_id,
        ref_number=ref_number,
        staff_user=staff,
    )
    return StandardResponse(data=GuestBookingDetail(**result))
