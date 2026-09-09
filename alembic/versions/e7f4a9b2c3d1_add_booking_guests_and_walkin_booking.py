"""add booking_guests table and walk-in booking support

Revision ID: e7f4a9b2c3d1
Revises: f532d80e2748
Create Date: 2026-09-01 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7f4a9b2c3d1"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create booking_guests table
    op.create_table(
        "booking_guests",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 2. Add booking_type enum type
    booking_type_enum = sa.Enum("ONLINE", "WALK_IN", name="bookingtype")
    booking_type_enum.create(op.get_bind(), checkfirst=True)

    # 3. Add new columns to bookings table
    op.add_column(
        "bookings",
        sa.Column(
            "booking_guest_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking_guests.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "booking_type",
            sa.Enum("ONLINE", "WALK_IN", name="bookingtype", native_enum=False, length=20),
            nullable=False,
            server_default="ONLINE",
        ),
    )

    # 4. Make guest_id nullable (was NOT NULL before)
    op.alter_column(
        "bookings",
        "guest_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # 5. Create indexes
    op.create_index(
        "ix_bookings_booking_guest_id",
        "bookings",
        ["booking_guest_id"],
    )


def downgrade() -> None:
    # 5. Drop indexes
    op.drop_index("ix_bookings_booking_guest_id", table_name="bookings")

    # 4. Restore guest_id to NOT NULL
    op.alter_column(
        "bookings",
        "guest_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    # 3. Drop new columns
    op.drop_column("bookings", "booking_type")
    op.drop_column("bookings", "booking_guest_id")

    # 2. Drop enum type
    sa.Enum(name="bookingtype").drop(op.get_bind(), checkfirst=True)

    # 1. Drop booking_guests table
    op.drop_table("booking_guests")
