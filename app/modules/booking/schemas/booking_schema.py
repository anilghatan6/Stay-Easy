import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator,model_validator


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


class UpdateSpecialRequest(BaseModel):
    special_requests: str = Field(..., max_length=1000)


class PaymentIntentRequest(BaseModel):
    payment_method: str = Field(default="ONLINE", max_length=20)
    payment_gateway: Optional[str] = Field(None, max_length=20)
    return_url: Optional[str] = Field(None, max_length=1000)
    advance_amount: Optional[float] = Field(
        None,
        ge=0,
        description="Required for ADVANCE payments. Must be between 10% and 50% of total_amount.",
    )

    @field_validator("payment_method", mode="before")
    @classmethod
    def uppercase_payment_method(cls, v: str) -> str:
        valid_methods = {"ONLINE", "ADVANCE", "PAY_ON_ARRIVAL"}
        v_upper = v.upper()
        if v_upper not in valid_methods:
            raise ValueError(
                f"Invalid payment method. Must be one of: {', '.join(valid_methods)}"
            )
        return v_upper
    
    @field_validator("payment_gateway", mode="before")
    @classmethod
    def uppercase_gateway(cls, v: str | None) -> str | None:
        if v is None:
            return None
        payment_gateways = {"STRIPE", "RAZORPAY", "KHALTI", "ESEWA"}
        v_upper = v.upper()
        if v_upper not in payment_gateways:
            raise ValueError(
                f"Invalid payment gateway. Must be one of: {', '.join(payment_gateways)}"
            )
        return v_upper
    @model_validator(mode="before")
    @classmethod
    def validate_payment_method_and_gateway(cls, values: dict) -> dict:
        payment_method = values.get("payment_method")
        payment_gateway = values.get("payment_gateway")
        advance_amount = values.get("advance_amount")

        if payment_method == "ADVANCE":
            if payment_gateway is None:
                raise ValueError("Payment gateway is required for ADVANCE payments.")

        if payment_method == "PAY_ON_ARRIVAL":
            if payment_gateway is not None or advance_amount is not None:
                raise ValueError("Payment gateway and advance amount are not required for PAY_ON_ARRIVAL payments.")

        return values


class PaymentIntentResponse(BaseModel):
    ref_number: str
    payment_gateway: Optional[str] = None
    payment_method: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    payment_status: Optional[str] = None
    amount_paid: Optional[float] = None
    amount_due: Optional[float] = None
    message: Optional[str] = None
    payment_intent_id: Optional[str] = None
    client_secret: Optional[str] = None
    order_id: Optional[str] = None
    payment_url: Optional[str] = None
    form_url: Optional[str] = None
    form_fields: Optional[dict] = None


class ConfirmPaymentRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=255)
    gateway_payload: dict = Field(
        default_factory=dict,
        description=(
            "Gateway-specific verification data from the frontend:\n"
            '- STRIPE: {"payment_intent_id": "pi_..."}\n'
            '- RAZORPAY: {"order_id": "...", "payment_id": "...", "signature": "..."}\n'
            '- KHALTI: {"pidx": "..."} or {"payment_intent_id": "..."}\n'
            '- ESEWA: {"data": "eyJ..."}'
        ),
    )


class ConfirmPaymentResponse(BaseModel):
    status: str
    message: Optional[str] = None
    booking_id: Optional[uuid.UUID] = None
    ref_number: Optional[str] = None


class PayRemainingRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=255)
    payment_gateway: str = Field(..., max_length=20)
    return_url: Optional[str] = Field(None, max_length=1000)
    gateway_payload: dict = Field(default_factory=dict)

    @field_validator("payment_gateway", mode="before")
    @classmethod
    def uppercase_gateway(cls, v: str) -> str:
        payment_gateways = {"STRIPE", "RAZORPAY", "KHALTI", "ESEWA"}
        v_upper = v.upper()
        if v_upper not in payment_gateways:
            raise ValueError(
                f"Invalid payment gateway. Must be one of: {', '.join(payment_gateways)}"
            )
        return v_upper


class RecordStaffPaymentRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount being paid")
    payment_method: str = Field(
        ...,
        max_length=50,
        description="How payment was collected: CASH, CARD_TERMINAL, BANK_TRANSFER, etc.",
    )
    notes: Optional[str] = Field(None, max_length=500)


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
    payment_method: str = "ONLINE"
    payment_status: str = "UNPAID"
    amount_paid: float = 0.0
    amount_due: float = 0.0
    advance_amount: Optional[float] = None
    min_advance_amount: Optional[float] = None
    max_advance_amount: Optional[float] = None
    min_advance_percentage: Optional[int] = None
    max_advance_percentage: Optional[int] = None
    property: PropertySummary
    rooms: list[RoomReservationDetail]
    total_amount: float
    subtotal: float = 0.0
    special_requests: Optional[str] = None
    special_offer_applied: list[AppliedSpecialOffer] = Field(default_factory=list)
    special_offer_discount: float = 0.0
    coupon_code: Optional[str] = None
    coupon_discount: float = 0.0
    soft_lock_expires_at: Optional[datetime] = None
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
    special_requests: Optional[str] = None
    currency: Optional[str]
    total_amount: Decimal
    created_at: datetime


class PaginatedBookingsResponse(BaseModel):
    items: list[BookingListItemResponse]
