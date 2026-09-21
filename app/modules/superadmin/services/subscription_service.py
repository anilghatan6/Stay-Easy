import uuid
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Optional

from app.modules.superadmin.repositories.subscription_repository import SubscriptionRepository
from app.modules.superadmin.repositories.audit_repository import AuditRepository
from app.modules.auth.models.users_model import User
from app.modules.auth.services.auth_services import AuthService
from app.utils.exceptions import (
    ServiceException,
    RepositoryException,
)
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class SubscriptionService:
    def __init__(
        self,
        db,
        subscription_repo: SubscriptionRepository,
        audit_repo: AuditRepository,
        auth_service: AuthService,
    ):
        self.db = db
        self.subscription_repo = subscription_repo
        self.audit_repo = audit_repo
        self.auth_service = auth_service

    # ─── Plans ───

    async def create_plan(self, data: dict, actor: User, ip_address: Optional[str] = None):
        existing = await self.subscription_repo.get_plan_by_slug(data["slug"])
        if existing:
            raise ServiceException(f"Plan with slug '{data['slug']}' already exists.")

        plan = await self.subscription_repo.create_plan(data)

        await self.audit_repo.log(
            actor_id=actor.id,
            actor_email=actor.email,
            action="create_plan",
            target_type="subscription_plan",
            target_id=plan.id,
            details={"name": plan.name, "slug": plan.slug, "price_monthly": str(plan.price_monthly)},
            ip_address=ip_address,
        )
        await self.db.commit()
        logger.info(f"[SubscriptionService] Plan created: {plan.id}")
        return plan

    async def get_plan(self, plan_id: uuid.UUID):
        plan = await self.subscription_repo.get_plan_by_id(plan_id)
        if plan is None:
            raise ServiceException("Plan not found.")
        return plan

    async def list_plans(self, include_inactive: bool = False):
        return await self.subscription_repo.list_plans(include_inactive)

    async def update_plan(self, plan_id: uuid.UUID, update_data: dict, actor: User, ip_address: Optional[str] = None):
        plan = await self.subscription_repo.update_plan(plan_id, update_data)
        if plan is None:
            raise ServiceException("Plan not found.")

        await self.audit_repo.log(
            actor_id=actor.id,
            actor_email=actor.email,
            action="update_plan",
            target_type="subscription_plan",
            target_id=plan_id,
            details=update_data,
            ip_address=ip_address,
        )
        await self.db.commit()
        logger.info(f"[SubscriptionService] Plan updated: {plan_id}")
        return plan

    async def deactivate_plan(self, plan_id: uuid.UUID, actor: User, ip_address: Optional[str] = None):
        deleted = await self.subscription_repo.deactivate_plan(plan_id)
        if not deleted:
            raise ServiceException("Plan not found.")

        await self.audit_repo.log(
            actor_id=actor.id,
            actor_email=actor.email,
            action="deactivate_plan",
            target_type="subscription_plan",
            target_id=plan_id,
            ip_address=ip_address,
        )
        await self.db.commit()
        logger.info(f"[SubscriptionService] Plan deactivated: {plan_id}")

    # ─── Tenant Subscriptions ───

    async def assign_subscription(
        self,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
        billing_cycle: str,
        actor: User,
        ip_address: Optional[str] = None,
    ):
        plan = await self.subscription_repo.get_plan_by_id(plan_id)
        if plan is None:
            raise ServiceException("Plan not found.")

        now = datetime.now(UTC)
        if billing_cycle == "YEARLY":
            expires_at = now + timedelta(days=365)
        else:
            expires_at = now + timedelta(days=30)

        sub = await self.subscription_repo.assign_subscription(
            tenant_id=tenant_id,
            plan_id=plan_id,
            billing_cycle=billing_cycle,
            starts_at=now,
            expires_at=expires_at,
        )

        await self.audit_repo.log(
            actor_id=actor.id,
            actor_email=actor.email,
            action="assign_subscription",
            target_type="tenant",
            target_id=tenant_id,
            details={
                "plan_name": plan.name,
                "billing_cycle": billing_cycle,
                "expires_at": expires_at.isoformat(),
            },
            ip_address=ip_address,
        )
        await self.db.commit()
        logger.info(f"[SubscriptionService] Subscription assigned: tenant {tenant_id} -> plan {plan.name}")
        return sub

    async def get_tenant_subscription(self, tenant_id: uuid.UUID):
        sub = await self.subscription_repo.get_tenant_subscription_with_plan(tenant_id)
        return sub

    # ─── Dashboard ───

    async def get_dashboard_metrics(self):
        return await self.subscription_repo.get_dashboard_metrics()
