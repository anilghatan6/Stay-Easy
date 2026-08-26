import uuid
from datetime import datetime, date

from sqlalchemy import ForeignKey, DateTime, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SqlEnum

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin
from app.modules.staff_mgmt.models.staffs_model import ShiftType


class StaffSchedule(Base, TimestampMixin):
    __tablename__ = "staff_schedules"

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

    shift_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    shift_type: Mapped[ShiftType] = mapped_column(
        SqlEnum(ShiftType, native_enum=False, length=10),
        nullable=False,
    )

    check_in_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    check_out_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    property: Mapped["Property"] = relationship("Property")
    staff: Mapped["Staff"] = relationship("Staff")
