import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field,model_validator
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
    payment_status: str
    payment_method: str
    amount_paid: float
    amount_due: float
    number_of_adults: int
    number_of_children: int
    checkin_date: date
    checkout_date: date
    checked_in_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None
    special_requests: Optional[str] = None
    property: PropertyInfo
    rooms: list[RoomInfo]
    guest: GuestInfo
    total_amount: float
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