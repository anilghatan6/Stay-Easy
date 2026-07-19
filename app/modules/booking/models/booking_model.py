from enum import StrEnum
import uuid
from datetime import date
from decimal import Decimal
from typing import List

from sqlalchemy import (
    ForeignKey,
    String,
    Numeric,
    Date,
    CheckConstraint,
    Enum as SqlEnum,
    UUID,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.utils.timestamp import TimestampMixin
from app.config.database_config import Base


class MasterBookingStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    CANCELLED = "CANCELLED"


class Booking(Base, TimestampMixin):
    """The parent record enforcing that a checkout belongs to exactly one property."""

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "checkout_date > checkin_date", name="chk_booking_dates_chronological"
        ),
        CheckConstraint("total_amount >= 0", name="chk_booking_total_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Enforces the rule: One booking event = One specific property
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    # Assuming your user table is named "users"
    guest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guests.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    status: Mapped[MasterBookingStatus] = mapped_column(
        SqlEnum(MasterBookingStatus, native_enum=False, length=30),
        default=MasterBookingStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Overall reservation timeline
    checkin_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    checkout_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    # Financial snapshot across all rooms booked in this transaction
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    ref_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )

    # Relationships
    property: Mapped["Property"] = relationship("Property")
    booking_rooms: Mapped[List["BookingRoom"]] = relationship(
        "BookingRoom", back_populates="booking", cascade="all, delete-orphan"
    )
    folios: Mapped[List["Folio"]] = relationship(
        "Folio", back_populates="booking", cascade="all, delete-orphan"
    )


class BookingRoom(Base, TimestampMixin):
    """Tracks each individual room allocated inside a parent booking record."""

    __tablename__ = "booking_rooms"


    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Points directly to your existing Rooms.id column
    room_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="booking_rooms")
    room_unit: Mapped["Rooms"] = relationship("Rooms")
