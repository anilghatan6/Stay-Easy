# app/modules/tasks/models/task_model.py

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, Enum as SqlEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class TaskType(StrEnum):
    ROOM_CLEANING = "ROOM_CLEANING"
    LINEN_CHANGE = "LINEN_CHANGE"
    MAINTENANCE_CHECK = "MAINTENANCE_CHECK"
    DEEP_CLEANING = "DEEP_CLEANING"
    INSPECTION = "INSPECTION"
    RESTOCK_AMENITIES = "RESTOCK_AMENITIES"
    OTHER = "OTHER"


class TaskPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    AWAITING_INSPECTION = "AWAITING_INSPECTION"


class HousekeepingTask(Base, TimestampMixin):
    __tablename__ = "housekeeping_tasks"
    __table_args__ = (
        CheckConstraint("due_time IS NOT NULL", name="chk_task_due_time_required"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), index=True, nullable=False
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )

    task_type: Mapped[TaskType] = mapped_column(
        SqlEnum(TaskType, native_enum=False, length=30), nullable=False
    )

    priority: Mapped[TaskPriority] = mapped_column(
        SqlEnum(TaskPriority, native_enum=False, length=10),
        default=TaskPriority.MEDIUM,
        nullable=False,
    )

    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(TaskStatus, native_enum=False, length=25),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )

    assigned_staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staffs.id", ondelete="CASCADE"), index=True, nullable=False
    )

    assigned_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    due_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    property: Mapped["Property"] = relationship("Property")
    room: Mapped["Rooms"] = relationship("Rooms")
    assigned_staff: Mapped["Staff"] = relationship("Staff", foreign_keys=[assigned_staff_id])
    assigned_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_by_id])