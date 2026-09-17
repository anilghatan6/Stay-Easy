import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.booking.models.booking_model import (
    Booking,
    BookingRoom,
    MasterBookingStatus,
    PaymentGateway,
)
from app.modules.pms.models.rooms_model import Rooms, RoomStatus, RoomType
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

BOOKING_ACTIVE_STATUSES = [
    MasterBookingStatus.CONFIRMED,
    MasterBookingStatus.CHECKED_IN,
    MasterBookingStatus.CHECKED_OUT,
]

OCCUPIED_ROOM_STATUSES = [
    RoomStatus.OCCUPIED,
    RoomStatus.BOOKED,
]


class DashboardRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_total_revenue(
        self, property_id: uuid.UUID, start_date: Optional[date] = None
    ) -> Decimal:
        logger.info(
            f"[DashboardRepository] Fetching total revenue for property {property_id}"
        )
        try:
            filters = [
                Booking.property_id == property_id,
                Booking.status.in_(BOOKING_ACTIVE_STATUSES),
            ]
            if start_date is not None:
                filters.append(Booking.checkin_date >= start_date)

            result = await self.db.execute(
                select(func.coalesce(func.sum(Booking.total_amount), Decimal("0.00")))
                .select_from(Booking)
                .where(*filters)
            )
            return result.scalar() or Decimal("0.00")
        except Exception as e:
            logger.error(f"[DashboardRepository] Failed to fetch total revenue: {e}")
            raise RepositoryException("Could not fetch total revenue.")

    async def get_arr(self, property_id: uuid.UUID) -> Decimal:
        logger.info(
            f"[DashboardRepository] Fetching ARR for property {property_id}"
        )
        try:
            thirty_days_ago = date.today() - timedelta(days=30)
            result = await self.db.execute(
                select(func.coalesce(func.sum(Booking.total_amount), Decimal("0.00")))
                .select_from(Booking)
                .where(
                    Booking.property_id == property_id,
                    Booking.status.in_(BOOKING_ACTIVE_STATUSES),
                    Booking.checkin_date >= thirty_days_ago,
                )
            )
            monthly_revenue = result.scalar() or Decimal("0.00")
            return monthly_revenue * 12
        except Exception as e:
            logger.error(f"[DashboardRepository] Failed to fetch ARR: {e}")
            raise RepositoryException("Could not fetch ARR.")

    async def get_occupancy_rate(self, property_id: uuid.UUID) -> float:
        logger.info(
            f"[DashboardRepository] Fetching occupancy rate for property {property_id}"
        )
        try:
            total_rooms_result = await self.db.execute(
                select(func.count())
                .select_from(Rooms)
                .where(Rooms.property_id == property_id)
            )
            total_rooms = total_rooms_result.scalar() or 0

            if total_rooms == 0:
                return 0.0

            occupied_rooms_result = await self.db.execute(
                select(func.count())
                .select_from(Rooms)
                .where(
                    Rooms.property_id == property_id,
                    Rooms.status.in_(OCCUPIED_ROOM_STATUSES),
                )
            )
            occupied_rooms = occupied_rooms_result.scalar() or 0

            return round((occupied_rooms / total_rooms) * 100, 1)
        except Exception as e:
            logger.error(
                f"[DashboardRepository] Failed to fetch occupancy rate: {e}"
            )
            raise RepositoryException("Could not fetch occupancy rate.")

    async def get_bookings_today(self, property_id: uuid.UUID) -> int:
        logger.info(
            f"[DashboardRepository] Fetching bookings today for property {property_id}"
        )
        try:
            today = date.today()
            result = await self.db.execute(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.property_id == property_id,
                    Booking.checkin_date == today,
                    Booking.status.in_(BOOKING_ACTIVE_STATUSES),
                )
            )
            return result.scalar() or 0
        except Exception as e:
            logger.error(
                f"[DashboardRepository] Failed to fetch bookings today: {e}"
            )
            raise RepositoryException("Could not fetch bookings today.")

    async def get_revenue_trend(
        self, property_id: uuid.UUID, days: int
    ) -> list[dict]:
        logger.info(
            f"[DashboardRepository] Fetching revenue trend for property {property_id}, "
            f"days={days}"
        )
        try:
            start_date = date.today() - timedelta(days=days - 1)
            result = await self.db.execute(
                select(
                    Booking.checkin_date.label("date"),
                    func.coalesce(func.sum(Booking.total_amount), Decimal("0.00")).label(
                        "revenue"
                    ),
                )
                .select_from(Booking)
                .where(
                    Booking.property_id == property_id,
                    Booking.status.in_(BOOKING_ACTIVE_STATUSES),
                    Booking.checkin_date >= start_date,
                )
                .group_by(Booking.checkin_date)
                .order_by(Booking.checkin_date.asc())
            )
            rows = result.all()
            revenue_by_date = {row.date: row.revenue for row in rows}

            trend = []
            for i in range(days):
                current_date = start_date + timedelta(days=i)
                trend.append(
                    {
                        "date": current_date,
                        "revenue": revenue_by_date.get(current_date, Decimal("0.00")),
                    }
                )
            return trend
        except Exception as e:
            logger.error(
                f"[DashboardRepository] Failed to fetch revenue trend: {e}"
            )
            raise RepositoryException("Could not fetch revenue trend.")

    async def get_revenue_by_room_type(
        self, property_id: uuid.UUID, days: int
    ) -> list[dict]:
        logger.info(
            f"[DashboardRepository] Fetching revenue by room type for property {property_id}, "
            f"days={days}"
        )
        try:
            start_date = date.today() - timedelta(days=days - 1)
            result = await self.db.execute(
                select(
                    RoomType.room_type_name.label("room_type_name"),
                    func.coalesce(func.sum(Booking.total_amount), Decimal("0.00")).label(
                        "revenue"
                    ),
                    func.count(Booking.id).label("booking_count"),
                )
                .select_from(RoomType)
                .join(Rooms, Rooms.room_type_id == RoomType.id)
                .outerjoin(BookingRoom, BookingRoom.room_unit_id == Rooms.id)
                .outerjoin(Booking, and_(
                    Booking.id == BookingRoom.booking_id,
                    Booking.property_id == property_id,
                    Booking.status.in_(BOOKING_ACTIVE_STATUSES),
                    Booking.checkin_date >= start_date,
                ))
                .where(Rooms.property_id == property_id)
                .group_by(RoomType.room_type_name)
                .order_by(func.sum(Booking.total_amount).desc())
            )
            rows = result.all()
            return [
                {
                    "room_type_name": row.room_type_name,
                    "revenue": row.revenue,
                    "booking_count": row.booking_count,
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(
                f"[DashboardRepository] Failed to fetch revenue by room type: {e}"
            )
            raise RepositoryException("Could not fetch revenue by room type.")

    async def get_booking_trend(
        self, property_id: uuid.UUID, days: int
    ) -> list[dict]:
        logger.info(
            f"[DashboardRepository] Fetching booking trend for property {property_id}, "
            f"days={days}"
        )
        try:
            start_date = date.today() - timedelta(days=days - 1)
            result = await self.db.execute(
                select(
                    Booking.checkin_date.label("date"),
                    func.count(Booking.id).label("booking_count"),
                )
                .select_from(Booking)
                .where(
                    Booking.property_id == property_id,
                    Booking.status.in_(BOOKING_ACTIVE_STATUSES),
                    Booking.checkin_date >= start_date,
                )
                .group_by(Booking.checkin_date)
                .order_by(Booking.checkin_date.asc())
            )
            rows = result.all()
            bookings_by_date = {row.date: row.booking_count for row in rows}

            trend = []
            for i in range(days):
                current_date = start_date + timedelta(days=i)
                trend.append(
                    {
                        "date": current_date,
                        "booking_count": bookings_by_date.get(current_date, 0),
                    }
                )
            return trend
        except Exception as e:
            logger.error(
                f"[DashboardRepository] Failed to fetch booking trend: {e}"
            )
            raise RepositoryException("Could not fetch booking trend.")

    async def get_top_channels(
        self, property_id: uuid.UUID
    ) -> list[dict]:
        logger.info(
            f"[DashboardRepository] Fetching top channels for property {property_id}"
        )
        try:
            result = await self.db.execute(
                select(
                    Booking.payment_gateway.label("channel_name"),
                    func.count(Booking.id).label("booking_count"),
                    func.coalesce(func.sum(Booking.total_amount), Decimal("0.00")).label(
                        "revenue"
                    ),
                )
                .select_from(Booking)
                .where(
                    Booking.property_id == property_id,
                    Booking.status.in_(BOOKING_ACTIVE_STATUSES),
                    Booking.payment_gateway.isnot(None),
                )
                .group_by(Booking.payment_gateway)
                .order_by(func.count(Booking.id).desc())
            )
            rows = result.all()
            return [
                {
                    "channel_name": row.channel_name.value if row.channel_name else "UNKNOWN",
                    "booking_count": row.booking_count,
                    "revenue": row.revenue,
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(
                f"[DashboardRepository] Failed to fetch top channels: {e}"
            )
            raise RepositoryException("Could not fetch top channels.")
