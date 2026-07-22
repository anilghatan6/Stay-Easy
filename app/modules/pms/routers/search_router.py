# router/search_router.py

from fastapi import APIRouter, Depends, Query, status, HTTPException
from datetime import date
from app.modules.pms.services.search_service import SearchService
from app.modules.pms.dependencies import get_search_service
from pydantic import BaseModel, Field
from uuid import UUID
from typing import List
from app.utils.schemas import StandardResponse


class PropertySearchItem(BaseModel):
    property_id: UUID
    name: str
    country: str
    state: str
    city: str
    address: str
    amenities: List[str]
    total_price: float
    nights: int

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    adults: int = Field(..., description="Number of adults requested")
    children: int = Field(..., description="Number of children requested")
    rooms: int = Field(..., description="Number of rooms requested")
    results: List[PropertySearchItem] = Field(
        default_factory=list, description="List of matched properties"
    )


router = APIRouter(prefix="/search", tags=["search"])


@router.get(
    "", response_model=StandardResponse[SearchResponse], status_code=status.HTTP_200_OK
)
async def search_properties(
    destination: str = Query(
        ...,
        description="Destination",
        max_length=100,
        min_length=2,
    ),
    check_in: date = Query(
        ...,
        description="Check in date",
        examples=["2024-01-01"],
    ),
    check_out: date = Query(..., description="Check out date", examples=["2024-01-01"]),
    adults: int = Query(1, description="Number of adults", ge=1, le=30),
    children: int = Query(0, description="Number of children", ge=0, le=15),
    rooms: int = Query(1, description="Number of rooms", ge=1, le=30),
    skip: int = Query(0, description="Number of records to skip", ge=0),
    limit: int = Query(10, description="Max records to return", ge=1, le=100),
    search_service: SearchService = Depends(get_search_service),
):
    if check_in >= check_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in date must be strictly before check-out date.",
        )
    service_result = await search_service.search(
        destination, check_in, check_out, adults, children, rooms, skip, limit
    )
    return StandardResponse(
        success=True,
        data=service_result["data"],
        meta=service_result["meta"],
    )
