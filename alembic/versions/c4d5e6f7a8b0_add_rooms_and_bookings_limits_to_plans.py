"""add rooms and bookings limits to subscription plans

Revision ID: c4d5e6f7a8b0
Revises: b3c4d5e6f7a8
Create Date: 2026-09-22 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b0'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column("max_rooms_per_property", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("max_bookings_per_month", sa.Integer(), nullable=False, server_default="50"),
    )


def downgrade() -> None:
    op.drop_column("subscription_plans", "max_bookings_per_month")
    op.drop_column("subscription_plans", "max_rooms_per_property")
