from fastapi import APIRouter, Depends, Query, status, HTTPException
from app.modules.pms.services.search_service import SearchService
from app.modules.pms.dependencies import get_search_service
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from typing import List
from app.utils.schemas import StandardResponse
from datetime import date, datetime, timezone, timedelta
from app.middlewares.rate_limiter import RateLimiter, bypass_global_limit


class PropertySearchItem(BaseModel):
    property_id: UUID
    name: str
    country: str
    state: str
    city: str
    address: str
    type: str
    cover_photo: str
    amenities: List[str]
    description: str
    currency: str
    total_price: float
    nights: int
    average_rating: float = 0.0
    

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    adults: int = Field(..., description="Number of adults requested")
    children: int = Field(..., description="Number of children requested")
    rooms: int = Field(..., description="Number of rooms requested")
    results: List[PropertySearchItem] = Field(
        default_factory=list, description="List of matched properties"
    )


router = APIRouter(prefix="/search", tags=["search"])


@router.get(
    "",
    response_model=StandardResponse[SearchResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="search")),
    ],
)
async def search_properties(
    destination: str = Query(
        ...,
        description="Destination",
        max_length=100,
        min_length=2,
    ),
    check_in: date = Query(
        datetime.now(timezone.utc).date(),
        description="Check in date",
        examples=["2026-01-01"],
    ),
    check_out: date = Query(
        datetime.now(timezone.utc).date() + timedelta(days=1),
        description="Check out date",
        examples=["2026-01-01"],
    ),
    adults: int = Query(2, description="Number of adults", ge=1, le=30),
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

    today = datetime.now(timezone.utc).date()

    if check_in < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in date cannot be in the past.",
        )
    service_result = await search_service.search(
        destination, check_in, check_out, adults, children, rooms, skip, limit
    )
    return StandardResponse(
        success=True,
        data=service_result["data"],
        meta=service_result["meta"],
    )


# fetch the max 20 properties which are near the guest location along with the distance from the guest location
@router.get(
    "/nearby",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="search/nearby")),
    ],
)
async def get_nearby_properties(
    lat: float = Query(
        ..., description="Latitude of the guest location", ge=-90, le=90
    ),
    lon: float = Query(
        ..., description="Longitude of the guest location", ge=-180, le=180
    ),
    limit: int = Query(10, description="Max properties to return", ge=1, le=50),
    search_service: SearchService = Depends(get_search_service),
):
    service_result = await search_service.get_nearby_properties(lat, lon, limit)
    return StandardResponse(
        success=True,
        data=service_result["results"],
        meta={
            "search_radius_km": service_result["search_radius_km"],
            "count": service_result["count"],
        },
    )
