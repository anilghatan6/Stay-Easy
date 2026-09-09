import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateFolioRequest(BaseModel):
    tax: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class UpdateFolioRequest(BaseModel):
    tax: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    discount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class AddChargeRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., decimal_places=2)
    category: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Free-form charge category, e.g. ROOM_CHARGE, DINING, SPA",
    )


class UpdateChargeRequest(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(None, decimal_places=2)
    category: Optional[str] = Field(None, min_length=1, max_length=50)


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
    guest_id: uuid.UUID
    status: str
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    settled_at: Optional[datetime] = None
    charges_count: int = 0
    created_at: datetime
    updated_at: datetime


class FolioDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    guest_id: uuid.UUID
    status: str
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
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
