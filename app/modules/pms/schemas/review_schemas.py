import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReviewCreateRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(None, max_length=2000)


class ReviewEditRequest(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=2000)


class ReviewResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    guest_name: str
    rating: int
    comment: Optional[str] = None
    is_edited: bool
    created_at: datetime
    updated_at: datetime


class ReviewSummaryResponse(BaseModel):
    average_rating: float
    total_reviews: int


class PaginatedReviewsResponse(BaseModel):
    reviews: list[ReviewResponse]
    average_rating: float
    total_reviews: int


class PropertySummaryResponse(BaseModel):
    id: uuid.UUID
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    photos: Optional[dict] = None


class GuestReviewResponse(BaseModel):
    id: uuid.UUID
    rating: int
    comment: Optional[str] = None
    is_edited: bool
    created_at: datetime
    updated_at: datetime
    property: PropertySummaryResponse


class PaginatedGuestReviewsResponse(BaseModel):
    reviews: list[GuestReviewResponse]
    total: int
