import uuid
from datetime import datetime, UTC
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    String,
    Boolean,
    UniqueConstraint,
    Integer,
    CheckConstraint,
    DateTime,
    ForeignKey,
)
from app.config.database_config import Base
from typing import Optional, List


class Guest(Base):
    """Global Registry for consumers supporting decentralized Multi-Tenant Single Sign-On (SSO)."""

    __tablename__ = "guests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships (Cross-Tenant loyalty profile intersections)
    loyalty_profiles: Mapped[List["GuestLoyalty"]] = relationship(
        "GuestLoyalty", back_populates="guest", cascade="all, delete-orphan"
    )


class GuestLoyalty(Base):
    """Intersection Table linking global identity vectors to operational Tenant domains."""

    __tablename__ = "guest_loyalty"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    guest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    loyalty_tier: Mapped[str] = mapped_column(
        String(50), default="Bronze", nullable=False
    )
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    guest: Mapped["Guest"] = relationship("Guest", back_populates="loyalty_profiles")
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="loyalty_profiles")

    # Enforce database restrictions (Unique combinations and positive balances)
    __table_args__ = (
        UniqueConstraint("guest_id", "tenant_id", name="uq_guest_tenant_loyalty"),
        CheckConstraint("total_points >= 0", name="chk_positive_points"),
    )
