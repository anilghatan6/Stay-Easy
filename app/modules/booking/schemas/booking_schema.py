import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BookingCreateRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=255)
    property_id: uuid.UUID
    room_ids: list[uuid.UUID] = Field(..., min_length=1)
    check_in: date
    check_out: date
    adults: int = Field(..., ge=1, le=30)
    children: int = Field(0, ge=0, le=15)


class ApplyDiscountRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)


class PaymentIntentRequest(BaseModel):
    payment_gateway: str = Field(..., max_length=20)
    return_url: Optional[str] = Field(None, max_length=255)

    @field_validator("payment_gateway", mode="before")
    @classmethod
    def uppercase_gateway(cls, v: str) -> str:
        payment_gateways = {"STRIPE", "RAZORPAY", "KHALTI"}
        v_upper = v.upper()
        if v_upper not in payment_gateways:
            raise ValueError(
                f"Invalid payment gateway. Must be one of: {', '.join(payment_gateways)}"
            )
        return v_upper


class PaymentIntentResponse(BaseModel):
    ref_number: str
    payment_gateway: str
    amount: float
    currency: str
    payment_intent_id: Optional[str] = None
    client_secret: Optional[str] = None
    order_id: Optional[str] = None
    payment_url: Optional[str] = None


class ConfirmPaymentRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=255)
    gateway_payload: dict = Field(
        default_factory=dict,
        description=(
            "Gateway-specific verification data from the frontend:\n"
            "- DUMMY: {} (ignored)\n"
            '- STRIPE: {"payment_intent_id": "pi_..."}\n'
            '- RAZORPAY: {"order_id": "...", "payment_id": "...", "signature": "..."}\n'
            '- KHALTI: {"pidx": "..."} or {"payment_intent_id": "..."}'
        ),
    )


class ConfirmPaymentResponse(BaseModel):
    status: str
    message: Optional[str] = None
    booking_id: Optional[uuid.UUID] = None
    ref_number: Optional[str] = None


class RoomReservationDetail(BaseModel):
    room_id: uuid.UUID
    room_name: str
    room_type: str
    bed_type: str
    max_adults: int
    max_children: int
    base_rate: float
    nights: int
    subtotal: float
    photo: str | None = None
    cancellation_title: str
    cancellation_description: str


class PropertySummary(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    city: Optional[str] = None
    country: Optional[str] = None
    currency: str = "USD"
    photo: str | None = None
    phone_number: str
    email: str


class AppliedSpecialOffer(BaseModel):
    title: str
    description: str


class BookingReservationResponse(BaseModel):
    booking_id: uuid.UUID
    ref_number: str
    status: str
    number_of_adults: int
    number_of_children: int
    check_in: date
    check_out: date
    nights: int
    payment_gateway: Optional[str] = None
    property: PropertySummary
    rooms: list[RoomReservationDetail]
    total_amount: float
    subtotal: float = 0.0
    special_offer_applied: list[AppliedSpecialOffer] = Field(default_factory=list)
    special_offer_discount: float = 0.0
    coupon_code: Optional[str] = None
    coupon_discount: float = 0.0
    soft_lock_expires_at: datetime
    created_at: datetime


class BookingListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID
    property_name: str
    property_photo: Optional[str]
    ref_number: str
    status: str
    number_of_adults: int
    number_of_children: int
    checkin_date: date
    checkout_date: date
    currency: Optional[str]
    total_amount: Decimal
    created_at: datetime


class PaginatedBookingsResponse(BaseModel):
    items: list[BookingListItemResponse]
