from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class SpecialOffer(Base, TimestampMixin):
    __tablename__ = "special_offers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Linked to your Property table (nullable=True means global system defaults if needed,
    # but strictly linked to property_id for custom and active property offers)
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    discount_percentage: Mapped[float] = mapped_column(
        Numeric(precision=5, scale=2), nullable=False, default=0.00
    )

    # Offer Dates * Constraints configuration
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # UI Toggles (Matches checked/unchecked radio circles )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    property: Mapped["Property"] = relationship(
        "Property", back_populates="special_offers"
    )

    # Database Constraints Frame
    __table_args__ = (
        # 1. Database Constraint: Ensures start date is strictly less than end date
        CheckConstraint("start_date < end_date", name="chk_offer_dates_chronology"),
        # 2. Database Constraint: Ensures discount percentage stays within normal logical boundaries
        CheckConstraint(
            "discount_percentage >= 0.00 AND discount_percentage <= 100.00",
            name="chk_offer_discount_range",
        ),
        # 3. Unique Identifier Constraint per Property Scope
        UniqueConstraint(
            "property_id", "title", name="uq_property_special_offers_title"
        ),
    )


