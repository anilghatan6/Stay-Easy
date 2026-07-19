from pydantic import field_validator
import uuid
from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TimestampSchema(BaseModel):
    created_at: datetime
    updated_at: datetime


class SpecialOfferBase(BaseModel):
    title: str = Field(
        ...,
        title="Offer Title",
        description="Title name of the special offer deal",
        min_length=2,
        max_length=100,
        examples=["Early Bird 15%"],
    )
    description: Optional[str] = Field(None, max_length=1000, title="Offer Description", description="Description of the special offer deal")
    discount_percentage: float = Field(
        float("0.00"),
        ge=0.00,
        le=100.00,
        title="Discount Percentage",
        description="Discount percentage of the special offer deal",
        examples=[15.00],
    )
    start_date: date = Field(..., title="Start Date", description="Active starting date window")
    end_date: date = Field(..., title="End Date", description="Active termination date window")
    is_active: bool = Field(default=False, title="Is Active", description="Is the special offer active")
    is_custom: bool = Field(default=False, title="Is Custom", description="Is the special offer custom")

    @model_validator(mode="after")
    def validate_offer_chronology(self) -> "SpecialOfferBase":
        """Validate date windows and prevent retroactive past schedules."""
        if self.start_date >= self.end_date:
            raise ValueError(
                "The offer start date must be strictly earlier than the end date."
            )

        if self.start_date < date.today():
            raise ValueError("The offer start date cannot be set in the past.")

        return self


# Bulk payload wrapper mapping array list
class SpecialOffersCreate(BaseModel):
    offers: List[SpecialOfferBase] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_unique_titles(self) -> "SpecialOffersCreate":
        """Prevent submitting multiple offers with identical titles in the same payload."""
        seen_titles = set()
        for offer in self.offers:
            normalized_title = offer.title.strip().lower()
            if normalized_title in seen_titles:
                raise ValueError(
                    f"Duplicate offer title found in request: '{offer.title}'. Titles must be unique."
                )
            seen_titles.add(normalized_title)
        return self


class SpecialOfferUpdate(BaseModel):
    title: Optional[str] = Field(
        None,
        title="Offer Title",
        description="Title name of the special offer deal",
        min_length=2,
        max_length=100,
        examples=["Early Bird 15%"],
    )
    description: Optional[str] = Field(None, max_length=1000, title="Offer Description", description="Description of the special offer deal")
    discount_percentage: Optional[float] = Field(
        None,
        ge=0.00,
        le=100.00,
        title="Discount Percentage",
        description="Discount percentage of the special offer deal",
        examples=[15.00],
    )
    start_date: Optional[date] = Field(None, title="Start Date", description="Active starting date window")
    end_date: Optional[date] = Field(None, title="End Date", description="Active termination date window")
    is_active: Optional[bool] = Field(None, title="Is Active", description="Is the special offer active")

    @model_validator(mode="after")
    def validate_offer_chronology(self) -> "SpecialOfferUpdate":
        """Validate date windows and prevent retroactive past schedules."""

        # Check start date constraint against today if provided
        if self.start_date and self.start_date < date.today():
            raise ValueError("The offer start date cannot be set in the past.")

        # Check range if both are present in the update payload
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValueError(
                    "The offer start date must be strictly earlier than the end date."
                )

        return self

    @field_validator("title",mode="after")
    @classmethod  
    def validate_title(cls,v:Optional[str])->Optional[str]:
        if v is None:
            return None
        v=v.strip()
        if len(v)<2:
            raise ValueError("Title must be at least 2 characters long")
        return v
    
    @field_validator("description",mode="after")
    @classmethod  
    def validate_description(cls,v:Optional[str])->Optional[str]:
        if v is None:
            return None
        v=v.strip()
        if len(v)>1000:
            raise ValueError("Description must be at most 1000 characters long")
        return v




class SpecialOfferResponse(TimestampSchema):
    id: uuid.UUID
    property_id: uuid.UUID
    title: str
    description: Optional[str]
    discount_percentage: float 
    start_date: date
    end_date: date
    is_active: bool
    is_custom: bool
    model_config = ConfigDict(from_attributes=True)