import uuid
from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
    field_serializer,
)


# 1. Shared Enum (Matches your Database Configuration)
class DiscountType(str, Enum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"

class DiscountCodeBase(BaseModel):
    code: str = Field(
        ...,
        title="Code",
        min_length=2,
        max_length=10,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Alphanumeric code",
    )
    type: DiscountType = Field(..., title="Discount Type")
    discount_value: float = Field(
        ...,
        title="Discount Value",
        gt=0,
        description="Discount value must be greater than 0",
    )
    min_amount: float = Field(
        default=0.0,
        title="Minimum Amount",
        ge=0,
        description="Minimum order amount must be 0 or positive",
    )
    max_uses: int = Field(
        ..., title="Maximum Uses", gt=0, description="Max uses must be greater than 0"
    )
    valid_from: date = Field(..., title="Valid From")
    valid_to: date = Field(..., title="Valid To")

    # 1. Single Field-level validation: Clean string modifications only
    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str) -> str:
        return v.strip().upper()

    # 2. Unified Model-level validation: All multi-field dependent rules go here
    @model_validator(mode="after")
    def validate_complex_business_rules(self) -> "DiscountCodeBase":
        # Rule A: Enforce chronological dates range validation
        if self.valid_to <= self.valid_from:
            raise ValueError(
                "The expiration date ('valid to') must occur strictly after the start date ('valid from')"
            )

        # Rule B: Percentage cap evaluation
        if self.type == DiscountType.PERCENTAGE and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100%")

        # Rule C: Fixed amount cap evaluation
        if self.type == DiscountType.FIXED:
            if self.discount_value > 100000:
                raise ValueError("Fixed discount value cannot exceed 100000")
            # Enforce that fixed deductions cannot be greater than the minimum spend threshold
            if self.discount_value > self.min_amount:
                raise ValueError(
                    "Fixed discount cannot be greater than the minimum required spend configuration"
                )

        return self


class DiscountCodeCreate(DiscountCodeBase):
    pass


class DiscountCodeUpdate(BaseModel):
    code: Optional[str] = Field(
        None, min_length=2, max_length=10, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    type: Optional[DiscountType] = None
    discount_value: Optional[float] = Field(None, gt=0)
    min_amount: Optional[float] = Field(None, ge=0)
    max_uses: Optional[int] = Field(None, gt=0)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip().upper()
        return v

    @model_validator(mode="after")
    def validate_update_fields(self) -> "DiscountCodeUpdate":
        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_to <= self.valid_from:
                raise ValueError(
                    "The expiration date ('valid to') must occur strictly after the start date ('valid from')"
                )

        if self.type is not None:
            if self.type == DiscountType.PERCENTAGE and self.discount_value is not None:
                if self.discount_value > 100:
                    raise ValueError("Percentage discount cannot exceed 100%")

            if self.type == DiscountType.FIXED:
                if self.discount_value is not None and self.discount_value > 100000:
                    raise ValueError("Fixed discount value cannot exceed 100000")

                if self.discount_value is not None and self.min_amount is not None:
                    if self.discount_value > self.min_amount:
                        raise ValueError(
                            "Fixed discount cannot be greater than the minimum required spend configuration"
                        )

        return self


class DiscountCodeResponse(DiscountCodeBase):
    id: uuid.UUID
    property_id: uuid.UUID
    used_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("valid_from", "valid_to", when_used="json")
    def serialize_dates(self, d: date) -> Optional[str]:
        return d.isoformat() if d else None
