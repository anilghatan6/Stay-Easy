import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal


class RoomInfo(BaseModel):
    room_id: uuid.UUID
    room_name: str
    room_type: str
    bed_type: str
    base_rate: float


class GuestInfo(BaseModel):
    guest_id: uuid.UUID
    full_name: str
    email: str
    phone: Optional[str] = None


class BookingGuestInfo(BaseModel):
    booking_guest_id: uuid.UUID
    full_name: str
    email: str
    phone: Optional[str] = None
    nationality: Optional[str] = None


class PropertyInfo(BaseModel):
    property_id: uuid.UUID
    name: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    always_allow_check_in_out: bool = False


class StaffBookingDetailResponse(BaseModel):
    booking_id: uuid.UUID
    ref_number: str
    status: str
    booking_type: str
    payment_status: str
    payment_method: str
    amount_paid: float
    amount_due: float
    refund_due: float
    number_of_adults: int
    number_of_children: int
    checkin_date: date
    checkout_date: date
    checked_in_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None
    special_requests: Optional[str] = None
    coupon_code: Optional[str] = None
    coupon_discount: float = 0.0
    property: PropertyInfo
    rooms: list[RoomInfo]
    guest: Optional[GuestInfo] = None
    booking_guest: Optional[BookingGuestInfo] = None
    total_amount: float
    subtotal: float
    created_at: datetime


class CheckInResponse(BaseModel):
    ref_number: str
    status: str
    checked_in_at: datetime
    property_name: str
    rooms: list[RoomInfo]
    guest_name: str
    message: str


class CheckOutResponse(BaseModel):
    ref_number: str
    status: str
    checked_out_at: datetime
    property_name: str
    rooms: list[RoomInfo]
    guest_name: str
    amount_due: float
    message: str


class ModifyBookingRequest(BaseModel):
    checkin_date: Optional[date] = None
    checkout_date: Optional[date] = None
    room_unit_ids: Optional[list[uuid.UUID]] = None
    number_of_adults: Optional[int] = None
    number_of_children: Optional[int] = None
    special_requests: Optional[str] = None
    reason: str  # required — why is staff making this change?

    @model_validator(mode="after")
    def check_dates(self):
        if self.checkin_date and self.checkout_date:
            if self.checkout_date <= self.checkin_date:
                raise ValueError("checkout_date must be after checkin_date")
        return self


class ModifyBookingResponse(BaseModel):
    ref_number: str
    checkin_date: date
    checkout_date: date
    total_amount: Decimal
    amount_paid: Decimal
    amount_due: Decimal
    refund_due: Decimal
    payment_status: str
    message: str


# ─────────────────────────── Walk-in Booking Schemas ─────────────────────────


class StaffCreateWalkinBookingRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=255)
    property_id: uuid.UUID
    room_ids: list[uuid.UUID] = Field(..., min_length=1)
    check_in: date
    check_out: date
    adults: int = Field(..., ge=1, le=30)
    children: int = Field(0, ge=0, le=15)

    # Guest contact info
    guest_full_name: str = Field(..., min_length=1, max_length=255)
    guest_email: str = Field(..., max_length=255)
    guest_phone: Optional[str] = Field(None, max_length=50)
    guest_nationality: Optional[str] = Field(None, max_length=100)

    # Financials
    coupon_code: Optional[str] = Field(None, max_length=50)
    payment_method: str = Field(default="PAY_ON_ARRIVAL", max_length=20)
    payment_gateway: Optional[str] = Field(None, max_length=20)
    amount_paid: Decimal = Field(default=Decimal("0.00"), ge=0)
    advance_amount: Optional[Decimal] = Field(None, ge=0)
    special_requests: Optional[str] = Field(None, max_length=1000)

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
        payment_gateways = { "KHALTI", "ESEWA", "BANK_TRANSFER", "CASH", "CARD"}
        v_upper = v.upper()
        if v_upper not in payment_gateways:
            raise ValueError(
                f"Invalid payment gateway. Must be one of: {', '.join(payment_gateways)}"
            )
        return v_upper

    @model_validator(mode="before")
    @classmethod
    def validate_payment_fields(cls, values: dict) -> dict:
        payment_method = values.get("payment_method", "PAY_ON_ARRIVAL")
        payment_gateway = values.get("payment_gateway")

        if payment_method and payment_method.upper() == "ADVANCE":
            if payment_gateway is None:
                raise ValueError(
                    "payment_gateway is required for ADVANCE payments."
                )

        return values


class StaffCancelBookingRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class StaffCreateWalkinBookingResponse(BaseModel):
    booking_id: uuid.UUID
    ref_number: str
    status: str
    booking_type: str
    number_of_adults: int
    number_of_children: int
    check_in: date
    check_out: date
    nights: int
    payment_method: str
    payment_status: str
    amount_paid: float
    amount_due: float
    advance_amount: Optional[float] = None
    total_amount: float
    subtotal: float
    coupon_code: Optional[str] = None
    coupon_discount: float = 0.0
    special_requests: Optional[str] = None
    property: PropertyInfo
    rooms: list[RoomInfo]
    booking_guest: BookingGuestInfo
    created_at: datetime


class StaffCancelBookingResponse(BaseModel):
    ref_number: str
    status: str
    message: str


# ─────────────────────────── Enum Response ─────────────────────────


class EnumResponse(BaseModel):
    value: str
    label: str


# ─────────────────────────── Activity Log ─────────────────────────


class ActivityLogResponse(BaseModel):
    id: uuid.UUID
    staff_name: str
    activity_type: str
    description: str
    booking_id: Optional[uuid.UUID] = None
    room_id: Optional[uuid.UUID] = None
    extra_data: Optional[dict] = None
    created_at: datetime


# ─────────────────────────── Today's Arrivals / Departures ─────────────────────────


class FrontDeskGuestInfo(BaseModel):
    guest_id: Optional[uuid.UUID] = None
    full_name: str
    email: str
    phone: Optional[str] = None
    nationality: Optional[str] = None


class FrontDeskBookingResponse(BaseModel):
    booking_id: uuid.UUID
    ref_number: str
    status: str
    booking_type: str
    guest: Optional[FrontDeskGuestInfo] = None
    rooms: list[RoomInfo]
    checkin_date: date
    checkout_date: date
    number_of_adults: int
    number_of_children: int
    special_requests: Optional[str] = None
    payment_method: str
    payment_status: str
    payment_gateway: Optional[str] = None
    amount_paid: float
    amount_due: float
    advance_amount: Optional[float] = None
    total_amount: float
    created_at: datetime


# ─────────────────────────── Front Desk Summary ─────────────────────────


class FrontDeskSummaryResponse(BaseModel):
    todays_arrivals: int
    todays_departures: int
    todays_checked_in: int
    todays_checked_out: int
    total_rooms: int
    total_available_rooms: int
    dirty_rooms: int
    occupied_rooms: int