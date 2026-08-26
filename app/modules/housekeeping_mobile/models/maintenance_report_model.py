import uuid
from enum import StrEnum

from sqlalchemy import String, ForeignKey, Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin
from app.utils.nested_mutable import NestedMutable
from app.modules.house_keeping.models.task_model import TaskPriority, TaskStatus


class MaintenanceCategory(StrEnum):
    PLUMBING = "PLUMBING"
    ELECTRICAL = "ELECTRICAL"
    HVAC = "HVAC"
    FURNITURE = "FURNITURE"
    APPLIANCE = "APPLIANCE"
    FLOORING = "FLOORING"
    PAINTING = "PAINTING"
    LOCK_SECURITY = "LOCK_SECURITY"
    OTHER = "OTHER"


class MaintenanceReport(Base, TimestampMixin):
    __tablename__ = "maintenance_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    category: Mapped[MaintenanceCategory] = mapped_column(
        SqlEnum(MaintenanceCategory, native_enum=False, length=20),
        nullable=False,
    )

    priority: Mapped[TaskPriority] = mapped_column(
        SqlEnum(TaskPriority, native_enum=False, length=10),
        default=TaskPriority.MEDIUM,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(String(2000), nullable=False)

    photos: Mapped[dict] = mapped_column(
        NestedMutable.as_mutable(JSONB),
        server_default='{"gallery": []}',
        nullable=False,
    )

    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(TaskStatus, native_enum=False, length=20),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )

    resolved_at: Mapped[dict] = mapped_column(
        String(30), nullable=True
    )

    # Relationships
    property: Mapped["Property"] = relationship("Property")
    room: Mapped["Rooms"] = relationship("Rooms")
    staff: Mapped["Staff"] = relationship("Staff", foreign_keys=[staff_id])
