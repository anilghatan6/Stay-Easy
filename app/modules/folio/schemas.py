import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateFolioRequest(BaseModel):
    tax: Decimal = Field(
        default=Decimal("0.00"), ge=0, le=100, decimal_places=2,
        description="Tax percentage (e.g., 18 for 18%)",
    )
    discount: Decimal = Field(
        default=Decimal("0.00"), ge=0, le=100, decimal_places=2,
        description="Discount percentage (e.g., 10 for 10%)",
    )


class UpdateFolioRequest(BaseModel):
    tax: Optional[Decimal] = Field(
        None, ge=0, le=100, decimal_places=2,
        description="Tax percentage (e.g., 18 for 18%)",
    )
    discount: Optional[Decimal] = Field(
        None, ge=0, le=100, decimal_places=2,
        description="Discount percentage (e.g., 10 for 10%)",
    )


class AddChargeRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(...,gt=Decimal("0.00"), decimal_places=2)
    category: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Free-form charge category, e.g. ROOM_CHARGE, DINING, SPA",
    )


class UpdateChargeRequest(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(None, gt=Decimal("0.00"), decimal_places=2)
    category: Optional[str] = Field(None, min_length=1, max_length=50)


class PayFolioRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Payment amount")
    payment_gateway: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Payment gateway: CASH, CARD, STRIPE, RAZORPAY, KHALTI, ESEWA, BANK_TRANSFER",
    )


class PayFolioResponse(BaseModel):
    folio_id: uuid.UUID
    folio_status: str
    folio_total: float
    amount_paid: float
    remaining_balance: float
    payment_status: str
    payment_gateway: Optional[str] = None
    message: str


class FolioChargeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    folio_id: uuid.UUID
    description: str
    amount: Decimal
    category: str
    posted_by: uuid.UUID
    posted_by_name: Optional[str] = None
    posted_at: datetime


class FolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    guest_id: Optional[uuid.UUID] = None
    guest_name: Optional[str] = None
    guest_email: Optional[str] = None
    status: str
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    amount_paid: float = 0.0
    remaining_balance: float = 0.0
    settled_at: Optional[datetime] = None
    charges_count: int = 0
    created_at: datetime
    updated_at: datetime


class FolioDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    guest_id: Optional[uuid.UUID] = None
    status: str
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    amount_paid: float = 0.0
    remaining_balance: float = 0.0
    settled_at: Optional[datetime] = None
    charges: List[FolioChargeResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FolioListResponse(BaseModel):
    folios: List[FolioResponse] = Field(default_factory=list)
    total: int
    skip: int
    limit: int
    has_more: bool
