import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import (
    DashboardOverviewResponse,
    RevenueTrendPoint,
    RevenueByRoomType,
    BookingTrendPoint,
    ChannelPerformance,
)
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class DashboardService:
    def __init__(
        self,
        db: AsyncSession,
        dashboard_repo: DashboardRepository,
    ):
        self.db = db
        self.dashboard_repo = dashboard_repo

    async def get_dashboard_overview(
        self,
        property_id: uuid.UUID,
    ) -> DashboardOverviewResponse:
        logger.info(
            f"[DashboardService] Fetching dashboard overview for property {property_id}"
        )

        total_revenue = await self.dashboard_repo.get_total_revenue(property_id)
        arr = await self.dashboard_repo.get_arr(property_id)
        occupancy_rate = await self.dashboard_repo.get_occupancy_rate(property_id)
        bookings_today = await self.dashboard_repo.get_bookings_today(property_id)

        top_channels_data = await self.dashboard_repo.get_top_channels(property_id)
        top_channels = [
            ChannelPerformance(
                channel_name=item["channel_name"],
                booking_count=item["booking_count"],
                revenue=item["revenue"],
            )
            for item in top_channels_data
        ]

        return DashboardOverviewResponse(
            total_revenue=total_revenue,
            arr=arr,
            occupancy_rate=occupancy_rate,
            bookings_today=bookings_today,
            top_channels=top_channels,
        )

    async def get_revenue_trend(
        self,
        property_id: uuid.UUID,
        days: int = 7,
    ) -> list[RevenueTrendPoint]:
        logger.info(
            f"[DashboardService] Fetching revenue trend for property {property_id}, "
            f"days={days}"
        )
        data = await self.dashboard_repo.get_revenue_trend(property_id, days)
        return [
            RevenueTrendPoint(date=item["date"], revenue=item["revenue"])
            for item in data
        ]

    async def get_revenue_by_room_type(
        self,
        property_id: uuid.UUID,
        days: int = 7,
    ) -> list[RevenueByRoomType]:
        logger.info(
            f"[DashboardService] Fetching revenue by room type for property {property_id}, "
            f"days={days}"
        )
        data = await self.dashboard_repo.get_revenue_by_room_type(property_id, days)
        return [
            RevenueByRoomType(
                room_type_name=item["room_type_name"],
                revenue=item["revenue"],
                booking_count=item["booking_count"],
            )
            for item in data
        ]

    async def get_booking_trend(
        self,
        property_id: uuid.UUID,
        days: int = 7,
    ) -> list[BookingTrendPoint]:
        logger.info(
            f"[DashboardService] Fetching booking trend for property {property_id}, "
            f"days={days}"
        )
        data = await self.dashboard_repo.get_booking_trend(property_id, days)
        return [
            BookingTrendPoint(
                date=item["date"], booking_count=item["booking_count"]
            )
            for item in data
        ]
