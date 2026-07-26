"""add discount columns to bookings

Revision ID: bb57c78b86d7
Revises: d8b0e07e4d0a
Create Date: 2026-07-23 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bb57c78b86d7"
down_revision: Union[str, Sequence[str], None] = "d8b0e07e4d0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0.00")))
    op.add_column("bookings", sa.Column("special_offer_discount", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0.00")))
    op.add_column("bookings", sa.Column("coupon_code", sa.String(50), nullable=True))
    op.add_column("bookings", sa.Column("coupon_discount", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0.00")))
    op.execute("UPDATE bookings SET subtotal = total_amount")


def downgrade() -> None:
    op.drop_column("bookings", "coupon_discount")
    op.drop_column("bookings", "coupon_code")
    op.drop_column("bookings", "special_offer_discount")
    op.drop_column("bookings", "subtotal")
