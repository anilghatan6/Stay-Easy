import uuid
from enum import StrEnum
from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, Enum as SqlEnum, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database_config import Base
from app.utils.timestamp import TimestampMixin
from app.utils.nested_mutable import NestedMutable


class CleaningChecklistItem(StrEnum):
    BED_MAKING = "BED_MAKING"
    BATHROOM_CLEANING = "BATHROOM_CLEANING"
    FLOOR_MOPPING = "FLOOR_MOPPING"
    DUSTING = "DUSTING"
    WINDOW_CLEANING = "WINDOW_CLEANING"
    TRASH_REMOVAL = "TRASH_REMOVAL"
    TOWEL_REPLACEMENT = "TOWEL_REPLACEMENT"
    AMENITIES_RESTOCK = "AMENITIES_RESTOCK"
    MIRROR_CLEANING = "MIRROR_CLEANING"
    MINIBAR_RESTOCK = "MINIBAR_RESTOCK"
    HVAC_CHECK = "HVAC_CHECK"
    DOOR_HANDLE_SANITIZING = "DOOR_HANDLE_SANITIZING"


class SupplierItem(StrEnum):
    TOWELS = "TOWELS"
    BED_SHEETS = "BED_SHEETS"
    PILLOW_CASES = "PILLOW_CASES"
    SHAMPOO = "SHAMPOO"
    CONDITIONER = "CONDITIONER"
    BODY_WASH = "BODY_WASH"
    HAND_SOAP = "HAND_SOAP"
    TOILET_PAPER = "TOILET_PAPER"
    TISSUE_BOX = "TISSUE_BOX"
    ECOKIT = "ECOKIT"
    WATER_BOTTLES = "WATER_BOTTLES"
    COFFEE_PODS = "COFFEE_PODS"
    TEA_BAGS = "TEA_BAGS"
    SLIPPERS = "SLIPPERS"
    ROBES = "ROBES"
    HAIR_DRYER = "HAIR_DRYER"
    IRON = "IRON"
    LAUNDRY_BAG = "LAUNDRY_BAG"
    SEWING_KIT = "SEWING_KIT"
    SHOE_SHINE = "SHOE_SHINE"


class CleaningSubmissionStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CleaningSubmission(Base, TimestampMixin):
    __tablename__ = "cleaning_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("housekeeping_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    checklist_items: Mapped[dict] = mapped_column(
        NestedMutable.as_mutable(JSONB),
        server_default='{"items": []}',
        nullable=False,
    )

    before_images: Mapped[dict] = mapped_column(
        NestedMutable.as_mutable(JSONB),
        server_default='{"gallery": []}',
        nullable=False,
    )

    after_images: Mapped[dict] = mapped_column(
        NestedMutable.as_mutable(JSONB),
        server_default='{"gallery": []}',
        nullable=False,
    )

    suppliers_used: Mapped[dict] = mapped_column(
        NestedMutable.as_mutable(JSONB),
        server_default='{"suppliers": []}',
        nullable=False,
    )

    status: Mapped[CleaningSubmissionStatus] = mapped_column(
        SqlEnum(CleaningSubmissionStatus, native_enum=False, length=20),
        default=CleaningSubmissionStatus.PENDING_REVIEW,
        nullable=False,
        index=True,
    )

    rejection_reason: Mapped[str] = mapped_column(
        String(500), nullable=True
    )

    reviewed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    task: Mapped["HousekeepingTask"] = relationship("HousekeepingTask")
    property: Mapped["Property"] = relationship("Property")
    room: Mapped["Rooms"] = relationship("Rooms")
    staff: Mapped["Staff"] = relationship("Staff", foreign_keys=[staff_id])
    reviewed_by: Mapped["User"] = relationship("User", foreign_keys=[reviewed_by_id])
