import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import String, ForeignKey, Enum as SqlEnum, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin
from app.modules.staff_mgmt.models.staffs_model import ShiftType


class SwapStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ShiftSwapRequest(Base, TimestampMixin):
    __tablename__ = "shift_swap_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    requester_staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    target_staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    requester_shift: Mapped[ShiftType] = mapped_column(
        SqlEnum(ShiftType, native_enum=False, length=10),
        nullable=False,
    )

    target_shift: Mapped[ShiftType] = mapped_column(
        SqlEnum(ShiftType, native_enum=False, length=10),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[SwapStatus] = mapped_column(
        SqlEnum(SwapStatus, native_enum=False, length=10),
        default=SwapStatus.PENDING,
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
    requester_staff: Mapped["Staff"] = relationship("Staff", foreign_keys=[requester_staff_id])
    target_staff: Mapped["Staff"] = relationship("Staff", foreign_keys=[target_staff_id])
    reviewed_by: Mapped["User"] = relationship("User", foreign_keys=[reviewed_by_id])
