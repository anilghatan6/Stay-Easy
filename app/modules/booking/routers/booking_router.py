from fastapi import APIRouter, Depends, Query, status, HTTPException
from typing import Annotated
from datetime import datetime, timezone
from app.modules.auth.auth_middlewares import CurrentGuest
from app.modules.booking.dependencies import get_booking_service
from app.modules.booking.services.booking_service import BookingService
from app.modules.booking.schemas.booking_schema import (
    ApplyDiscountRequest,
    BookingCreateRequest,
    BookingReservationResponse,
    ConfirmPaymentRequest,
    ConfirmPaymentResponse,
    PaginatedBookingsResponse,
    PaymentIntentRequest,
    PaymentIntentResponse,

)
from app.utils.schemas import StandardResponse
from app.utils.exceptions import BookingException
router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: BookingCreateRequest,
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
):

    if body.check_in >= body.check_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in date must be strictly before check-out date.",
        )

    today = datetime.now(timezone.utc).date()

    if body.check_in < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in date cannot be in the past.",
        )
    result = await booking_service.create_booking(
        idempotency_key=body.idempotency_key,
        guest_id=guest.id,
        property_id=body.property_id,
        room_ids=body.room_ids,
        check_in=body.check_in,
        check_out=body.check_out,
        adults=body.adults,
        children=body.children,
    )
    return StandardResponse(data=BookingReservationResponse(**result))


@router.post("/{ref_number}/payment-intent")
async def create_payment_intent(
    ref_number: str,
    body: PaymentIntentRequest,
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
):
    result = await booking_service.create_payment_intent(
        ref_number=ref_number,
        payment_gateway=body.payment_gateway,
    )
    return StandardResponse(data=PaymentIntentResponse(**result))


@router.post("/{ref_number}/confirm")
async def confirm_payment(
    ref_number: str,
    body: ConfirmPaymentRequest,
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
):
    result = await booking_service.confirm_payment(
        idempotency_key=body.idempotency_key,
        ref_number=ref_number,
        gateway_payload=body.gateway_payload,
    )
    payment_data = ConfirmPaymentResponse(**result)
    filtered_data = payment_data.model_dump(exclude_none=True)
    return StandardResponse(data=filtered_data)


@router.post("/{ref_number}/apply-discount")
async def apply_discount(
    ref_number: str,
    body: ApplyDiscountRequest,
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
):
    result = await booking_service.apply_discount_code(
        ref_number=ref_number,
        guest_id=guest.id,
        coupon_code=body.code,
    )
    return StandardResponse(data=BookingReservationResponse(**result))


# @router.delete("/{ref_number}/discount")
# async def remove_discount(
#     ref_number: str,
#     guest: CurrentGuest,
#     booking_service: Annotated[BookingService, Depends(get_booking_service)],
# ):
#     result = await booking_service.remove_discount_code(
#         ref_number=ref_number,
#         guest_id=guest.id,
#     )
#     return StandardResponse(data=BookingReservationResponse(**result))


@router.get("/me")
async def get_my_bookings(
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    result = await booking_service.get_guest_bookings(guest.id, page, limit)
    return StandardResponse(data=PaginatedBookingsResponse(**result))


@router.get("/{ref_number}")
async def get_booking(
    ref_number: str,
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
):
    result = await booking_service.get_booking_detail(ref_number, guest.id)
    if result is None:
        raise BookingException("Booking not found")
    return StandardResponse(data=BookingReservationResponse(**result))
