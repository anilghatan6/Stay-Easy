import uuid
from datetime import datetime, UTC
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.superadmin.models.tenant_subscription_model import (
    TenantSubscription,
    SubscriptionStatus,
)
from app.modules.superadmin.models.subscription_plan_model import SubscriptionPlan
from app.modules.pms.models.properties_model import Property
from app.modules.staff_mgmt.models.staffs_model import Staff
from app.modules.pms.models.rooms_model import Rooms
from app.modules.booking.models.booking_model import Booking, MasterBookingStatus
from app.utils.exceptions import PlanLimitExceededException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


@dataclass
class PlanLimits:
    max_properties: int
    max_staff: int
    max_rooms_per_property: int
    max_bookings_per_month: int
    features: dict | None


@dataclass
class ResourceUsage:
    max: int
    used: int


@dataclass
class UsageSummary:
    properties: ResourceUsage
    staff: ResourceUsage
    rooms_per_property: dict[uuid.UUID, ResourceUsage]  # property_id -> usage
    bookings_this_month: ResourceUsage
    features: list[str]


UNLIMITED = 999999


class PlanEnforcementService:
    """Validates tenant resource usage against their subscription plan limits."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_active_subscription(self, tenant_id: uuid.UUID) -> TenantSubscription:
        stmt = (
            select(TenantSubscription)
            .options(selectinload(TenantSubscription.plan))
            .where(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        result = await self.db.execute(stmt)
        sub = result.scalar_one_or_none()

        if sub is None:
            raise PlanLimitExceededException(
                "No active subscription found. Please subscribe to a plan."
            )

        if sub.expires_at and sub.expires_at < datetime.now(UTC):
            raise PlanLimitExceededException(
                "Your subscription has expired. Please renew to continue."
            )

        return sub

    def _get_limits(self, sub: TenantSubscription) -> PlanLimits:
        plan = sub.plan
        return PlanLimits(
            max_properties=plan.max_properties,
            max_staff=plan.max_staff,
            max_rooms_per_property=plan.max_rooms_per_property,
            max_bookings_per_month=plan.max_bookings_per_month,
            features=plan.features or {},
        )

    async def _count_properties(self, tenant_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Property)
            .where(Property.tenant_id == tenant_id)
        )
        return result.scalar_one() or 0

    async def _count_staff(self, tenant_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Staff)
            .where(Staff.tenant_id == tenant_id)
        )
        return result.scalar_one() or 0

    async def _count_rooms_in_property(self, property_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Rooms)
            .where(Rooms.property_id == property_id)
        )
        return result.scalar_one() or 0

    async def _count_bookings_this_month(self, tenant_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(func.count())
            .select_from(Booking)
            .join(Property, Property.id == Booking.property_id)
            .where(
                Property.tenant_id == tenant_id,
                Booking.created_at >= month_start,
                Booking.status.notin_([
                    MasterBookingStatus.CANCELLED,
                    MasterBookingStatus.EXPIRED,
                ]),
            )
        )
        return result.scalar_one() or 0

    # ─── Public enforcement methods ───

    async def check_property_limit(self, tenant_id: uuid.UUID) -> None:
        sub = await self._get_active_subscription(tenant_id)
        limits = self._get_limits(sub)

        if limits.max_properties >= UNLIMITED:
            return

        used = await self._count_properties(tenant_id)
        if used >= limits.max_properties:
            raise PlanLimitExceededException(
                f"Property limit reached ({limits.max_properties}). "
                "Upgrade your plan to add more properties."
            )

    async def check_staff_limit(self, tenant_id: uuid.UUID) -> None:
        sub = await self._get_active_subscription(tenant_id)
        limits = self._get_limits(sub)

        if limits.max_staff >= UNLIMITED:
            return

        used = await self._count_staff(tenant_id)
        if used >= limits.max_staff:
            raise PlanLimitExceededException(
                f"Staff limit reached ({limits.max_staff}). "
                "Upgrade your plan to add more staff."
            )

    async def check_room_limit(self, tenant_id: uuid.UUID, property_id: uuid.UUID) -> None:
        sub = await self._get_active_subscription(tenant_id)
        limits = self._get_limits(sub)

        if limits.max_rooms_per_property >= UNLIMITED:
            return

        used = await self._count_rooms_in_property(property_id)
        if used >= limits.max_rooms_per_property:
            raise PlanLimitExceededException(
                f"Room limit per property reached ({limits.max_rooms_per_property}). "
                "Upgrade your plan for more rooms."
            )

    async def check_booking_limit(self, tenant_id: uuid.UUID) -> None:
        sub = await self._get_active_subscription(tenant_id)
        limits = self._get_limits(sub)

        if limits.max_bookings_per_month >= UNLIMITED:
            return

        used = await self._count_bookings_this_month(tenant_id)
        if used >= limits.max_bookings_per_month:
            raise PlanLimitExceededException(
                f"Monthly booking limit reached ({limits.max_bookings_per_month}). "
                "Upgrade your plan for more bookings."
            )

    async def check_feature(self, tenant_id: uuid.UUID, feature_key: str) -> None:
        sub = await self._get_active_subscription(tenant_id)
        limits = self._get_limits(sub)

        if not limits.features.get(feature_key, False):
            raise PlanLimitExceededException(
                f"Feature '{feature_key}' is not available on your current plan. "
                "Upgrade to access this feature."
            )

    async def get_usage_summary(self, tenant_id: uuid.UUID) -> UsageSummary:
        sub = await self._get_active_subscription(tenant_id)
        limits = self._get_limits(sub)

        prop_count = await self._count_properties(tenant_id)
        staff_count = await self._count_staff(tenant_id)
        booking_count = await self._count_bookings_this_month(tenant_id)

        # Get room usage per property
        props_stmt = select(Property.id).where(Property.tenant_id == tenant_id)
        props_result = await self.db.execute(props_stmt)
        property_ids = props_result.scalars().all()

        rooms_per_property = {}
        for pid in property_ids:
            room_count = await self._count_rooms_in_property(pid)
            rooms_per_property[pid] = ResourceUsage(
                max=limits.max_rooms_per_property,
                used=room_count,
            )

        enabled_features = [
            k for k, v in (limits.features or {}).items() if v is True
        ]

        return UsageSummary(
            properties=ResourceUsage(max=limits.max_properties, used=prop_count),
            staff=ResourceUsage(max=limits.max_staff, used=staff_count),
            rooms_per_property=rooms_per_property,
            bookings_this_month=ResourceUsage(
                max=limits.max_bookings_per_month, used=booking_count
            ),
            features=enabled_features,
        )
