import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Numeric, Date, ForeignKey, CheckConstraint,UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SqlEnum
from app.utils.nested_mutable import NestedMutable 
from app.utils.timestamp import TimestampMixin 
from enum import StrEnum
from app.config.database_config import Base


class JobRole(StrEnum):
    MANAGER = "MANAGER"
    FRONT_DESK = "FRONT_DESK"
    HOUSEKEEPING = "HOUSEKEEPING"
    WAITER = "WAITER"
    KITCHEN = "KITCHEN"
    MAINTENANCE = "MAINTENANCE"


class StaffStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ON_LEAVE = "ON_LEAVE"


class Staff(Base, TimestampMixin):
    __tablename__ = "staffs"
    __table_args__ = (
        CheckConstraint("monthly_salary >= 0", name="chk_staff_salary_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


    job_role: Mapped[JobRole] = mapped_column(
        SqlEnum(JobRole, native_enum=False, length=30),
        nullable=False,
    )

    monthly_salary: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    joining_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[StaffStatus] = mapped_column(
        SqlEnum(StaffStatus, native_enum=False, length=20),
        default=StaffStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # Format: {"profile": "url", "citizenship_front": "url", "citizenship_back": "url"}
    photos: Mapped[Dict[str, Any]] = mapped_column(
        NestedMutable.as_mutable(JSONB),
        server_default='{"profile": null, "citizenship_front": null, "citizenship_back": null}',
        nullable=False,
    )

    # ─── Relationships ──────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="staffs")

    property_assignments: Mapped[List["StaffProperty"]] = relationship(
        "StaffProperty", back_populates="staff", cascade="all, delete-orphan"
    )



class StaffProperty(Base, TimestampMixin):
    __tablename__ = "staff_properties"
    __table_args__ = (
        UniqueConstraint("staff_id", "property_id", name="uq_staff_property"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Relationships
    staff: Mapped["Staff"] = relationship("Staff", back_populates="property_assignments")
    property: Mapped["Property"] = relationship("Property")