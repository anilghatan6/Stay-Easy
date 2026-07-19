
from app.config.database_config import Base
from sqlalchemy import String, ForeignKey, Numeric,  DateTime, CheckConstraint, Enum as SqlEnum,UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import uuid
from enum import StrEnum
from app.utils.timestamp import TimestampMixin


class FolioStatus(StrEnum):
    OPEN = "OPEN"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    WAIVED = "WAIVED"

class Folio(Base, TimestampMixin):
    """Financial tracking card assigned directly to a guest's stay window."""
    __tablename__ = "folios"
    __table_args__ = (
        CheckConstraint("total >= 0", name="chk_folio_total_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT"), index=True, nullable=False)
    guest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    
    status: Mapped[FolioStatus] = mapped_column(SqlEnum(FolioStatus, native_enum=False, length=20), default=FolioStatus.OPEN, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="folios")
    charges: Mapped[List["FolioCharge"]] = relationship("FolioCharge", back_populates="folio", cascade="all, delete-orphan")


class FolioCharge(Base, TimestampMixin):
    """Itemized costs (room base rates, incidentals, restaurant bills) added to a folio."""
    __tablename__ = "folio_charges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("folios.id", ondelete="CASCADE"), index=True, nullable=False)
    
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., "ROOM_CHARGE", "SPA", "DINING"
    posted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    folio: Mapped["Folio"] = relationship("Folio", back_populates="charges")