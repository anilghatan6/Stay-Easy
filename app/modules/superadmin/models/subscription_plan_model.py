import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Numeric, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class SubscriptionPlan(Base, TimestampMixin):
    """Platform subscription pricing plans."""

    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    price_yearly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    max_properties: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_staff: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_rooms_per_property: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_bookings_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    features: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
