import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, Query

from app.middlewares.auth_middlewares import CurrentUser
from app.modules.dashboard.dependencies import get_dashboard_service
from app.modules.dashboard.schemas import (
    DashboardOverviewResponse,
    RevenueTrendPoint,
    RevenueByRoomType,
    BookingTrendPoint,
)
from app.modules.dashboard.service import DashboardService
from app.utils.schemas import StandardResponse

router = APIRouter(
    prefix="/properties",
    tags=["Analytics"],
)


@router.get(
    "/{property_id}/analytics",
    response_model=StandardResponse[DashboardOverviewResponse],
    description="Get dashboard overview: total revenue, ARR, occupancy rate, bookings today, and top performing channels",
)
async def get_dashboard_overview(
    property_id: uuid.UUID,
    staff: CurrentUser,
    dashboard_service: DashboardService = Depends(get_dashboard_service),
):
    result = await dashboard_service.get_dashboard_overview(
        property_id=property_id,
    )
    return StandardResponse(data=result)


@router.get(
    "/{property_id}/analytics/revenue-trend",
    response_model=StandardResponse[List[RevenueTrendPoint]],
    description="Get revenue trend over a number of days",
)
async def get_revenue_trend(
    property_id: uuid.UUID,
    staff: CurrentUser,
    days: Annotated[
        int,
        Query(ge=1, le=30, description="Number of days for trends (max 30)"),
    ] = 7,
    dashboard_service: DashboardService = Depends(get_dashboard_service),
):
    result = await dashboard_service.get_revenue_trend(
        property_id=property_id,
        days=days,
    )
    return StandardResponse(data=result)


@router.get(
    "/{property_id}/analytics/revenue-by-room-type",
    response_model=StandardResponse[List[RevenueByRoomType]],
    description="Get revenue breakdown by room type over a number of days",
)
async def get_revenue_by_room_type(
    property_id: uuid.UUID,
    staff: CurrentUser,
    days: Annotated[
        int,
        Query(ge=1, le=30, description="Number of days for trends (max 30)"),
    ] = 7,
    dashboard_service: DashboardService = Depends(get_dashboard_service),
):
    result = await dashboard_service.get_revenue_by_room_type(
        property_id=property_id,
        days=days,
    )
    return StandardResponse(data=result)


@router.get(
    "/{property_id}/analytics/booking-trend",
    response_model=StandardResponse[List[BookingTrendPoint]],
    description="Get booking trend over a number of days",
)
async def get_booking_trend(
    property_id: uuid.UUID,
    staff: CurrentUser,
    days: Annotated[
        int,
        Query(ge=1, le=30, description="Number of days for trends (max 30)"),
    ] = 7,
    dashboard_service: DashboardService = Depends(get_dashboard_service),
):
    result = await dashboard_service.get_booking_trend(
        property_id=property_id,
        days=days,
    )
    return StandardResponse(data=result)
