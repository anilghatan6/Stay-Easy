from fastapi import APIRouter, Depends, Query, status, HTTPException
from app.modules.pms.services.search_service import SearchService
from app.modules.pms.dependencies import get_search_service
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from typing import List, Optional
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
    total_reviews:int = 0
    allow_pay_on_arrival:bool = False
    

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    adults: int = Field(..., description="Number of adults requested")
    children: int = Field(..., description="Number of children requested")
    rooms: int = Field(..., description="Number of rooms requested")
    results: List[PropertySearchItem] = Field(
        default_factory=list, description="List of matched properties"
    )


class SystemRoomTypeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_type_name: str
    is_default: bool


class SystemBedTypeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bed_name: str
    is_default: bool


class SystemAmenityItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    icon: Optional[str] = None


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

    min_price: float | None = Query(None, description="Min price per room/night", ge=0, le=100000000),
    max_price: float | None = Query(None, description="Max price per room/night", ge=0, le=100000000),
    room_type_ids: list[UUID] | None = Query(None, description="Filter by room type(s)"),
    bed_type_ids: list[UUID] | None = Query(None, description="Filter by bed type(s)"),
    amenity_ids: list[UUID] | None = Query(None, description="Filter by system amenity(ies)"),

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
    
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "min_price cannot be greater than max_price.")

    service_result = await search_service.search(
        destination, check_in, check_out, adults, children, rooms, skip, limit,
        min_price=min_price,
        max_price=max_price,
        room_type_ids=room_type_ids,
        bed_type_ids=bed_type_ids,
        amenity_ids=amenity_ids,
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


@router.get(
    "/system-room-types",
    response_model=StandardResponse[List[SystemRoomTypeItem]],
    status_code=status.HTTP_200_OK,
    summary="Get system-wide default room types",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="search/system-room-types")),
    ],
)
async def get_system_room_types(
    search_service: SearchService = Depends(get_search_service),
):
    room_types = await search_service.get_system_room_types()
    return StandardResponse(success=True, data=room_types)


@router.get(
    "/system-bed-types",
    response_model=StandardResponse[List[SystemBedTypeItem]],
    status_code=status.HTTP_200_OK,
    summary="Get system-wide default bed types",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="search/system-bed-types")),
    ],
)
async def get_system_bed_types(
    search_service: SearchService = Depends(get_search_service),
):
    bed_types = await search_service.get_system_bed_types()
    return StandardResponse(success=True, data=bed_types)


@router.get(
    "/system-amenities",
    response_model=StandardResponse[List[SystemAmenityItem]],
    status_code=status.HTTP_200_OK,
    summary="Get all system-wide amenities",
    dependencies=[
        Depends(bypass_global_limit),
        Depends(RateLimiter(max_requests=30, window_seconds=60, scope="search/system-amenities")),
    ],
)
async def get_system_amenities(
    search_service: SearchService = Depends(get_search_service),
):
    amenities = await search_service.get_system_amenities()
    return StandardResponse(success=True, data=amenities)

