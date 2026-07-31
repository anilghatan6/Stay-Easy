from datetime import datetime
from sqlalchemy import DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column, declared_attr


class TimestampMixin:
  
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Use @declared_attr to dynamically generate the index per table
    @declared_attr
    def __table_args__(cls):
        return (
            Index(f"idx_{cls.__tablename__}_created_at_desc", cls.created_at.desc()),
        )
