import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    ForeignKey,
    Integer,
    CheckConstraint,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class Review(Base, TimestampMixin):
    """Guest review for a property, linked to a specific booking."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_review_per_booking"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="chk_review_rating_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    guest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    comment: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    property: Mapped["Property"] = relationship("Property", back_populates="reviews")
    guest: Mapped["Guest"] = relationship("Guest")
    booking: Mapped["Booking"] = relationship("Booking")
