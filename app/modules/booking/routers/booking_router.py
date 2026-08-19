from fastapi import APIRouter, Depends, Query, status, HTTPException, BackgroundTasks, Request
from typing import Annotated
from datetime import datetime, timezone
from app.middlewares.auth_middlewares import CurrentGuest
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
    UpdateSpecialRequest,
)
from app.utils.schemas import StandardResponse
from app.utils.exceptions import BookingException
from app.middlewares.rate_limiter import RateLimiter, bypass_global_limit

router = APIRouter(
    prefix="/bookings",
    tags=["bookings"],
)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=15, window_seconds=60, scope="booking")),
    ],
)
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


@router.post(
    "/{ref_number}/payment-intent",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(
            RateLimiter(
                max_requests=15, window_seconds=60, scope="create_payment_intent"
            )
        ),
    ],
)
async def create_payment_intent(
    ref_number: str,
    body: PaymentIntentRequest,
    request: Request,
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
):
    origin = request.headers.get("host")
    result = await booking_service.create_payment_intent(
        ref_number=ref_number,
        payment_gateway=body.payment_gateway,
        return_url=origin,
        guest_id=guest.id,
    )
    return StandardResponse(data=PaymentIntentResponse(**result))


@router.post(
    "/{ref_number}/confirm",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(
            RateLimiter(max_requests=15, window_seconds=60, scope="confirm_booking")
        ),
    ],
)
async def confirm_payment(
    ref_number: str,
    body: ConfirmPaymentRequest,
    guest: CurrentGuest,
    background_tasks: BackgroundTasks,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
):
    result = await booking_service.confirm_payment(
        idempotency_key=body.idempotency_key,
        ref_number=ref_number,
        gateway_payload=body.gateway_payload,
        guest_id=guest.id,
        background_tasks=background_tasks,
    )
    payment_data = ConfirmPaymentResponse(**result)
    filtered_data = payment_data.model_dump(exclude_none=True)

    return StandardResponse(data=filtered_data)


@router.post(
    "/{ref_number}/apply-discount",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(
            RateLimiter(max_requests=15, window_seconds=60, scope="apply_discount")
        ),
    ],
)
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


@router.patch(
    "/{ref_number}/special-requests",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(
            RateLimiter(max_requests=15, window_seconds=60, scope="update_booking")
        ),
    ],
)
async def update_special_requests(
    ref_number: str,
    body: UpdateSpecialRequest,
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
):
    result = await booking_service.update_special_requests(
        ref_number=ref_number,
        guest_id=guest.id,
        special_requests=body.special_requests,
    )
    return result
    
@router.get("/me")
async def get_my_bookings(
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
    skip: int = Query(0, ge=0, description="Number of bookings to skip"),
    limit: int = Query(10, ge=1, le=50, description="Max number of bookings to return"),
):
    result = await booking_service.get_guest_bookings(guest.id, skip, limit)
    has_more = skip + len(result["bookings"]) < result["total"]

    return StandardResponse(
        data=PaginatedBookingsResponse(items=result["bookings"]),
        meta={
            "total": result["total"],
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        },
    )


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


@router.delete(
    "/{ref_number}",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(
            RateLimiter(max_requests=15, window_seconds=60, scope="delete_booking")
        ),
    ],
)
async def delete_booking(
    ref_number: str,
    guest: CurrentGuest,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
):
    response = await booking_service.delete_booking(ref_number, guest.id)
    return response
