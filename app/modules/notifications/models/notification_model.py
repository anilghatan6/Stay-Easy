import uuid
from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Enum as SqlEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class NotificationType(StrEnum):
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    WALKIN_BOOKING_CREATED = "WALKIN_BOOKING_CREATED"
    BOOKING_CHECKED_IN = "BOOKING_CHECKED_IN"
    BOOKING_CHECKED_OUT = "BOOKING_CHECKED_OUT"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_MODIFIED = "BOOKING_MODIFIED"

    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_CANCELLED = "TASK_CANCELLED"
    CLEANING_SUBMITTED = "CLEANING_SUBMITTED"
    CLEANING_APPROVED = "CLEANING_APPROVED"
    CLEANING_REJECTED = "CLEANING_REJECTED"

    ROOM_DIRTY = "ROOM_DIRTY"
    ROOM_MAINTENANCE = "ROOM_MAINTENANCE"
    ROOM_AVAILABLE = "ROOM_AVAILABLE"

    MAINTENANCE_REPORTED = "MAINTENANCE_REPORTED"
    MAINTENANCE_RESOLVED = "MAINTENANCE_RESOLVED"

    SWAP_REQUESTED = "SWAP_REQUESTED"
    LEAVE_REQUESTED = "LEAVE_REQUESTED"
    LEAVE_STATUS_CHANGED = "LEAVE_STATUS_CHANGED"


class NotificationPriority(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Notification(Base, TimestampMixin):
    """A single notification event. Fans out to N recipients via NotificationRecipient."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
    )

    type: Mapped[NotificationType] = mapped_column(
        SqlEnum(NotificationType, native_enum=False, length=40),
        nullable=False,
        index=True,
    )

    priority: Mapped[NotificationPriority] = mapped_column(
        SqlEnum(NotificationPriority, native_enum=False, length=10),
        default=NotificationPriority.INFO,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)

    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    actor_guest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guests.id", ondelete="SET NULL"),
        nullable=True,
    )

    meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    actor: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[actor_user_id]
    )
    guest_actor: Mapped[Optional["Guest"]] = relationship(
        "Guest", foreign_keys=[actor_guest_id]
    )
    recipients: Mapped[list["NotificationRecipient"]] = relationship(
        "NotificationRecipient",
        back_populates="notification",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_notifications_property_created", "property_id", "created_at"),
        Index("ix_notifications_org_created", "organization_id", "created_at"),
    )


class NotificationRecipient(Base):
    """Fan-out row per user per notification. Read state is per-user."""

    __tablename__ = "notification_recipients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    notification: Mapped["Notification"] = relationship(
        "Notification", back_populates="recipients"
    )

    __table_args__ = (
        UniqueConstraint(
            "notification_id", "user_id", name="uq_notification_recipient"
        ),
        Index("ix_notif_recipient_user_read", "user_id", "is_read"),
    )
