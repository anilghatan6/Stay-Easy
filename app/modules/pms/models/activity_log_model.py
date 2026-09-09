import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class PropertyActivityLog(Base, TimestampMixin):
    """Immutable activity log tracking all property-level operations."""

    __tablename__ = "property_activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    staff_name: Mapped[str] = mapped_column(String(255), nullable=False)

    activity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    description: Mapped[str] = mapped_column(String(500), nullable=False)

    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    room_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
    )

    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
