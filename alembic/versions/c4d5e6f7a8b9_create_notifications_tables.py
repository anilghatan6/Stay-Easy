"""create notifications and notification_recipients tables

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-18 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Notification type enum
    notification_type_enum = sa.Enum(
        "BOOKING_CREATED", "BOOKING_CONFIRMED", "WALKIN_BOOKING_CREATED",
        "BOOKING_CHECKED_IN", "BOOKING_CHECKED_OUT", "BOOKING_CANCELLED", "BOOKING_MODIFIED",
        "TASK_ASSIGNED", "TASK_STARTED", "TASK_COMPLETED", "TASK_CANCELLED",
        "CLEANING_SUBMITTED", "CLEANING_APPROVED", "CLEANING_REJECTED",
        "ROOM_DIRTY", "ROOM_MAINTENANCE", "ROOM_AVAILABLE",
        "MAINTENANCE_REPORTED", "MAINTENANCE_RESOLVED",
        "SWAP_REQUESTED", "LEAVE_REQUESTED", "LEAVE_STATUS_CHANGED",
        name="notificationtype",
        native_enum=False,
        length=40,
    )

    # Notification priority enum
    notification_priority_enum = sa.Enum(
        "INFO", "WARNING", "CRITICAL",
        name="notificationpriority",
        native_enum=False,
        length=10,
    )

    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", UUID(as_uuid=True), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", notification_type_enum, nullable=False),
        sa.Column("priority", notification_priority_enum, nullable=False, server_default="INFO"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index("ix_notifications_property_created", "notifications", ["property_id", sa.text("created_at")])
    op.create_index("ix_notifications_org_created", "notifications", ["organization_id", sa.text("created_at")])

    op.create_table(
        "notification_recipients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_id", UUID(as_uuid=True), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notif_recipient_user_read", "notification_recipients", ["user_id", "is_read"])
    op.create_unique_constraint("uq_notification_recipient", "notification_recipients", ["notification_id", "user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_notification_recipient", "notification_recipients", type_="unique")
    op.drop_index("ix_notif_recipient_user_read", table_name="notification_recipients")
    op.drop_table("notification_recipients")
    op.drop_index("ix_notifications_org_created", table_name="notifications")
    op.drop_index("ix_notifications_property_created", table_name="notifications")
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_table("notifications")
    sa.Enum(name="notificationtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notificationpriority").drop(op.get_bind(), checkfirst=True)
