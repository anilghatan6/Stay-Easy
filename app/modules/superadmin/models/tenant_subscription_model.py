import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import String, DateTime, ForeignKey, Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class SubscriptionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    PAST_DUE = "PAST_DUE"


class BillingCycle(StrEnum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class TenantSubscription(Base, TimestampMixin):
    """Links a tenant to a subscription plan."""

    __tablename__ = "tenant_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[SubscriptionStatus] = mapped_column(
        SqlEnum(SubscriptionStatus, native_enum=False, length=20),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )

    billing_cycle: Mapped[BillingCycle] = mapped_column(
        SqlEnum(BillingCycle, native_enum=False, length=10),
        default=BillingCycle.MONTHLY,
        nullable=False,
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped["Tenant"] = relationship("Tenant")
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan")
