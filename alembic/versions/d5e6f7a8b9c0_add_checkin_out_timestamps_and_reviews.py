"""add check-in/out timestamps and reviews table

Revision ID: d5e6f7a8b9c0
Revises: c3f8a2b1d4e5
Create Date: 2026-08-24 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c3f8a2b1d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add check-in/check-out timestamps to bookings
    op.add_column(
        "bookings",
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add rating fields to properties
    op.add_column(
        "properties",
        sa.Column("average_rating", sa.Numeric(3, 2), nullable=True, server_default=sa.text("0.00")),
    )
    op.add_column(
        "properties",
        sa.Column("total_reviews", sa.Integer(), nullable=True, server_default=sa.text("0")),
    )

    # Create reviews table
    op.create_table(
        "reviews",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "property_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "guest_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("guests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "booking_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(2000), nullable=True),
        sa.Column("is_edited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("booking_id", name="uq_review_per_booking"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="chk_review_rating_range"),
    )


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_column("properties", "total_reviews")
    op.drop_column("properties", "average_rating")
    op.drop_column("bookings", "checked_out_at")
    op.drop_column("bookings", "checked_in_at")
