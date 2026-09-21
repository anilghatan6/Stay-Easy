import uuid
from typing import Optional

from sqlalchemy import String, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin


class FeatureFlag(Base, TimestampMixin):
    """Platform-wide feature toggles."""

    __tablename__ = "feature_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
