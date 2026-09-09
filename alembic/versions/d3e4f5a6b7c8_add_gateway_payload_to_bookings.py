"""add gateway_payload to bookings

Revision ID: d3e4f5a6b7c8
Revises: 625a9b743fd5, b1c2d3e4f5a6
Create Date: 2026-09-03 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = ("625a9b743fd5", "b1c2d3e4f5a6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("gateway_payload", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bookings", "gateway_payload")
