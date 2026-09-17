from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class RevenueTrendPoint(BaseModel):
    date: date
    revenue: Decimal


class RevenueByRoomType(BaseModel):
    room_type_name: str
    revenue: Decimal
    booking_count: int


class BookingTrendPoint(BaseModel):
    date: date
    booking_count: int


class ChannelPerformance(BaseModel):
    channel_name: str
    booking_count: int
    revenue: Decimal


class DashboardOverviewResponse(BaseModel):
    total_revenue: Decimal
    arr: Decimal
    occupancy_rate: float
    bookings_today: int
    top_channels: list[ChannelPerformance]
