import uuid
from datetime import date
from sqlalchemy import (
    String,
    Numeric,
    Integer,
    ForeignKey,
    Date,
    CheckConstraint,
    UniqueConstraint,
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from enum import StrEnum
from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class DiscountType(StrEnum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"


class DiscountCode(Base, TimestampMixin):
    __tablename__ = "discount_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )

    # Financial Configuration
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[DiscountType] = mapped_column(SqlEnum(DiscountType), nullable=False)
    discount_value: Mapped[float] = mapped_column(
        Numeric(precision=10, scale=2), nullable=False
    )
    min_amount: Mapped[float] = mapped_column(
        Numeric(precision=10, scale=2), default=0.00, nullable=False
    )

    # Usage Counters
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Time Constraints
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        # Ensures a property owner cannot create two identical codes for the same property
        UniqueConstraint("property_id", "code", name="uq_property_discount_code"),
        # Enforces that valid_to must always occur after valid_from chronologically
        CheckConstraint("valid_to >= valid_from", name="check_valid_date_range"),
        # Ensures that a discount value cannot be negative
        CheckConstraint("discount_value >= 0", name="check_positive_discount_value"),
        # Ensures minimal spend is a positive constraint
        CheckConstraint("min_amount >= 0", name="check_positive_min_amount"),
        # Prevents used counts from extending past max allowances
        CheckConstraint("used_count <= max_uses", name="check_max_uses_limit"),
    )
