import uuid
from datetime import datetime, date
from enum import StrEnum

from sqlalchemy import String, ForeignKey, Enum as SqlEnum, DateTime, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class LeaveType(StrEnum):
    SICK_LEAVE = "SICK_LEAVE"
    PERSONAL_LEAVE = "PERSONAL_LEAVE"
    VACATION = "VACATION"
    UNPAID_LEAVE = "UNPAID_LEAVE"
    OTHER = "OTHER"


class LeaveStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class LeaveRequest(Base, TimestampMixin):
    __tablename__ = "leave_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    leave_type: Mapped[LeaveType] = mapped_column(
        SqlEnum(LeaveType, native_enum=False, length=20),
        nullable=False,
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    reason: Mapped[str] = mapped_column(String(1000), nullable=False)

    status: Mapped[LeaveStatus] = mapped_column(
        SqlEnum(LeaveStatus, native_enum=False, length=10),
        default=LeaveStatus.PENDING,
        nullable=False,
        index=True,
    )

    reviewed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    property: Mapped["Property"] = relationship("Property")
    staff: Mapped["Staff"] = relationship("Staff", foreign_keys=[staff_id])
    reviewed_by: Mapped["User"] = relationship("User", foreign_keys=[reviewed_by_id])
