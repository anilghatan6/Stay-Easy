# app/modules/favorites/models.py

import uuid
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin

class GuestFavorite(Base,TimestampMixin):
    __tablename__ = "guest_favorites"

    guest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guests.id", ondelete="CASCADE"), primary_key=True
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True
    )
