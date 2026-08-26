"""add payment method and status columns to bookings

Revision ID: c3f8a2b1d4e5
Revises: add_password_flag
Create Date: 2026-08-24 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3f8a2b1d4e5"
down_revision: Union[str, Sequence[str], None] = "add_password_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    payment_method_enum = sa.Enum("ONLINE", "ADVANCE", "PAY_ON_ARRIVAL", name="paymentmethod")
    payment_method_enum.create(op.get_bind(), checkfirst=True)

    payment_status_enum = sa.Enum("UNPAID", "PARTIAL", "PAID", name="paymentstatus")
    payment_status_enum.create(op.get_bind(), checkfirst=True)

    # Add new columns
    op.add_column(
        "bookings",
        sa.Column(
            "payment_method",
            sa.Enum("ONLINE", "ADVANCE", "PAY_ON_ARRIVAL", name="paymentmethod"),
            nullable=False,
            server_default="ONLINE",
        ),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "payment_status",
            sa.Enum("UNPAID", "PARTIAL", "PAID", name="paymentstatus"),
            nullable=False,
            server_default="UNPAID",
        ),
    )
    op.add_column(
        "bookings",
        sa.Column("amount_paid", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0.00")),
    )
    op.add_column(
        "bookings",
        sa.Column("amount_due", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0.00")),
    )
    op.add_column(
        "bookings",
        sa.Column("advance_amount", sa.Numeric(10, 2), nullable=True),
    )

    # Backfill amount_due for existing bookings
    op.execute("UPDATE bookings SET amount_due = total_amount WHERE amount_due = 0")


def downgrade() -> None:
    op.drop_column("bookings", "advance_amount")
    op.drop_column("bookings", "amount_due")
    op.drop_column("bookings", "amount_paid")
    op.drop_column("bookings", "payment_status")
    op.drop_column("bookings", "payment_method")

    sa.Enum(name="paymentstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="paymentmethod").drop(op.get_bind(), checkfirst=True)
