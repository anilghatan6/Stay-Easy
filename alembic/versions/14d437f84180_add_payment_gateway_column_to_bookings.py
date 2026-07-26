"""add payment_gateway column to bookings

Revision ID: 14d437f84180
Revises: bb57c78b86d7
Create Date: 2026-07-26 13:03:13.302477

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14d437f84180'
down_revision: Union[str, Sequence[str], None] = 'bb57c78b86d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings",
        sa.Column("payment_gateway", sa.String(20), nullable=False, server_default="DUMMY")
    )


def downgrade() -> None:
    op.drop_column("bookings", "payment_gateway")
