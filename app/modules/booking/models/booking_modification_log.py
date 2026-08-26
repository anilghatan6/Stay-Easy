# app/modules/pms/models/booking_modification_log.py

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin

class BookingModificationLog(Base, TimestampMixin):
    """Immutable audit trail of staff-initiated changes to a booking."""

    __tablename__ = "booking_modification_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),  # adjust FK target to your staff/User table
        index=True,
        nullable=False,
    )

    # Snapshots let you reconstruct exactly what changed without re-deriving it from a diff later
    before_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    after_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Redundant but handy for quick filtering/search without parsing JSON, e.g. "show me all date changes"
    changed_fields: Mapped[str] = mapped_column(String(500), nullable=False)

    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)



    # Relationships
    booking: Mapped["Booking"] = relationship("Booking")
    staff: Mapped["User"] = relationship("User")