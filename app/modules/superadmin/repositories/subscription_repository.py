import uuid
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.superadmin.models.subscription_plan_model import SubscriptionPlan
from app.modules.superadmin.models.tenant_subscription_model import TenantSubscription
from app.modules.pms.models.tenants_model import Tenant
from app.modules.auth.models.users_model import User
from app.modules.booking.models.booking_model import Booking
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class SubscriptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Plans ───

    async def create_plan(self, data: dict) -> SubscriptionPlan:
        try:
            plan = SubscriptionPlan(**data)
            self.db.add(plan)
            await self.db.flush()
            await self.db.refresh(plan)
            return plan
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to create plan: {e}")
            raise RepositoryException("Failed to create plan.")

    async def get_plan_by_id(self, plan_id: uuid.UUID) -> Optional[SubscriptionPlan]:
        try:
            stmt = select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to fetch plan: {e}")
            raise RepositoryException("Failed to fetch plan.")

    async def get_plan_by_slug(self, slug: str) -> Optional[SubscriptionPlan]:
        try:
            stmt = select(SubscriptionPlan).where(SubscriptionPlan.slug == slug)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to fetch plan by slug: {e}")
            raise RepositoryException("Failed to fetch plan.")

    async def list_plans(self, include_inactive: bool = False) -> list[SubscriptionPlan]:
        try:
            stmt = select(SubscriptionPlan).order_by(SubscriptionPlan.price_monthly.asc())
            if not include_inactive:
                stmt = stmt.where(SubscriptionPlan.is_active == True)
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to list plans: {e}")
            raise RepositoryException("Failed to list plans.")

    async def update_plan(self, plan_id: uuid.UUID, update_data: dict) -> Optional[SubscriptionPlan]:
        try:
            plan = await self.get_plan_by_id(plan_id)
            if plan is None:
                return None
            for field, value in update_data.items():
                setattr(plan, field, value)
            await self.db.flush()
            await self.db.refresh(plan)
            return plan
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to update plan: {e}")
            raise RepositoryException("Failed to update plan.")

    async def deactivate_plan(self, plan_id: uuid.UUID) -> bool:
        try:
            plan = await self.get_plan_by_id(plan_id)
            if plan is None:
                return False
            plan.is_active = False
            await self.db.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to deactivate plan: {e}")
            raise RepositoryException("Failed to deactivate plan.")

    # ─── Tenant Subscriptions ───

    async def assign_subscription(
        self,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
        billing_cycle: str,
        starts_at: datetime,
        expires_at: Optional[datetime] = None,
    ) -> TenantSubscription:
        try:
            # Check existing subscription
            existing = await self.get_tenant_subscription(tenant_id)
            if existing:
                # Update existing subscription
                existing.plan_id = plan_id
                existing.billing_cycle = billing_cycle
                existing.starts_at = starts_at
                existing.expires_at = expires_at
                existing.status = "ACTIVE"
                await self.db.flush()
                await self.db.refresh(existing)
                return existing

            sub = TenantSubscription(
                tenant_id=tenant_id,
                plan_id=plan_id,
                billing_cycle=billing_cycle,
                starts_at=starts_at,
                expires_at=expires_at,
            )
            self.db.add(sub)
            await self.db.flush()
            await self.db.refresh(sub)
            return sub
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to assign subscription: {e}")
            raise RepositoryException("Failed to assign subscription.")

    async def get_tenant_subscription(
        self, tenant_id: uuid.UUID
    ) -> Optional[TenantSubscription]:
        try:
            stmt = (
                select(TenantSubscription)
                .where(TenantSubscription.tenant_id == tenant_id)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to fetch subscription: {e}")
            raise RepositoryException("Failed to fetch subscription.")

    async def get_tenant_subscription_with_plan(
        self, tenant_id: uuid.UUID
    ) -> Optional[TenantSubscription]:
        try:
            stmt = (
                select(TenantSubscription)
                .options(selectinload(TenantSubscription.plan))
                .where(TenantSubscription.tenant_id == tenant_id)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to fetch subscription: {e}")
            raise RepositoryException("Failed to fetch subscription.")

    # ─── Dashboard Metrics ───

    async def get_dashboard_metrics(self) -> dict:
        try:
            # Total tenants
            result = await self.db.execute(select(func.count()).select_from(Tenant))
            total_tenants = result.scalar_one()

            # Active tenants (with at least one property)
            from app.modules.pms.models.properties_model import Property

            stmt = select(func.count(func.distinct(Tenant.id))).select_from(Tenant).join(
                Property, Property.tenant_id == Tenant.id
            )
            result = await self.db.execute(stmt)
            active_tenants = result.scalar_one()

            # Total users
            result = await self.db.execute(select(func.count()).select_from(User))
            total_users = result.scalar_one()

            # Total properties
            result = await self.db.execute(select(func.count()).select_from(Property))
            total_properties = result.scalar_one()

            # Total bookings
            result = await self.db.execute(select(func.count()).select_from(Booking))
            total_bookings = result.scalar_one()

            # Total revenue
            result = await self.db.execute(
                select(func.coalesce(func.sum(Booking.total_amount), Decimal("0.00")))
            )
            total_revenue = result.scalar_one()

            # New signups this month
            now = datetime.now(UTC)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            result = await self.db.execute(
                select(func.count())
                .select_from(User)
                .where(User.created_at >= month_start)
            )
            new_signups = result.scalar_one()

            # Active subscriptions
            result = await self.db.execute(
                select(func.count())
                .select_from(TenantSubscription)
                .where(TenantSubscription.status == "ACTIVE")
            )
            active_subscriptions = result.scalar_one()

            return {
                "total_tenants": total_tenants or 0,
                "active_tenants": active_tenants or 0,
                "total_users": total_users or 0,
                "total_properties": total_properties or 0,
                "total_bookings": total_bookings or 0,
                "total_revenue": total_revenue or Decimal("0.00"),
                "new_signups_this_month": new_signups or 0,
                "active_subscriptions": active_subscriptions or 0,
            }
        except SQLAlchemyError as e:
            logger.error(f"[SubscriptionRepo] Failed to get dashboard metrics: {e}")
            raise RepositoryException("Failed to get dashboard metrics.")
