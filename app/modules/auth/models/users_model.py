import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from app.config.database_config import Base
from typing import Optional, List
from datetime import datetime, UTC
from app.modules.pms.models.tenants_model import Tenant


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=True,  # Nullable because Admins exist briefly before creating a Tenant
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    # Relationships
    # 1. The workspace this user works inside (Applies to Admins AND Staff)
    workspace: Mapped[Optional["Tenant"]] = relationship(
        "Tenant", foreign_keys=[tenant_id], back_populates="staff_members"
    )

    # 2. The workspaces this user legally OWNS (Applies to Admins only)
    owned_tenants: Mapped[List["Tenant"]] = relationship(
        "Tenant", foreign_keys="[Tenant.owner_id]", back_populates="owner"
    )
