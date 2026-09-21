import uuid
from datetime import datetime, UTC
from enum import StrEnum

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SqlEnum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database_config import Base
from typing import Optional

class AnnouncementTarget(StrEnum):
    ALL = "ALL"
    SELECTED = "SELECTED"


class Announcement(Base):
    """Platform-wide announcements sent to admins."""

    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    priority: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)

    target: Mapped[AnnouncementTarget] = mapped_column(
        SqlEnum(AnnouncementTarget, native_enum=False, length=10),
        default=AnnouncementTarget.ALL,
        nullable=False,
    )

    target_admin_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    send_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
