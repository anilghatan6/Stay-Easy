import uuid
from datetime import datetime, UTC
from sqlalchemy import String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.config.database_config import Base
from app.modules.auth.models.users_model import User
from app.modules.auth.models.guests_model import Guest



class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND guest_id IS NULL) OR "
            "(user_id IS NULL AND guest_id IS NOT NULL)",
            name="chk_reset_token_exactly_one_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    guest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guests.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Hash of the temp password itself — never store it in plaintext, even here.
    # Used to detect whether a login attempt's password matches an active temp password.
    temp_password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Set the instant the temp password is successfully used to log in.
    # Once set, this temp password can never be used again — enforces one-time use.
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="reset_tokens")
    guest: Mapped[Optional["Guest"]] = relationship("Guest", back_populates="reset_tokens")

    @property
    def account_id(self) -> uuid.UUID:
        return self.user_id if self.user_id is not None else self.guest_id

    @property
    def is_valid(self) -> bool:
        """True only if unused AND not expired — the one-time, 15-minute window."""
        return self.used_at is None and self.expires_at > datetime.now(UTC)