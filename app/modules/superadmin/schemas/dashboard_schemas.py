from typing import Optional
from decimal import Decimal


class DashboardResponse:
    def __init__(
        self,
        total_tenants: int,
        active_tenants: int,
        total_users: int,
        total_properties: int,
        total_bookings: int,
        total_revenue: Decimal,
        new_signups_this_month: int,
        active_subscriptions: int,
        pending_subscriptions: int,
    ):
        self.total_tenants = total_tenants
        self.active_tenants = active_tenants
        self.total_users = total_users
        self.total_properties = total_properties
        self.total_bookings = total_bookings
        self.total_revenue = total_revenue
        self.new_signups_this_month = new_signups_this_month
        self.active_subscriptions = active_subscriptions
        self.pending_subscriptions = pending_subscriptions


class HealthResponse:
    def __init__(
        self,
        status: str,
        db_status: str,
        redis_status: str,
        uptime_seconds: float,
        total_users: int,
        total_tenants: int,
        total_bookings: int,
        active_subscriptions: int,
    ):
        self.status = status
        self.db_status = db_status
        self.redis_status = redis_status
        self.uptime_seconds = uptime_seconds
        self.total_users = total_users
        self.total_tenants = total_tenants
        self.total_bookings = total_bookings
        self.active_subscriptions = active_subscriptions
