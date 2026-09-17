"""make folio guest_id nullable for walk-in bookings

Revision ID: a1b2c3d4e5a6
Revises: d3e4f5a6b7c8
Create Date: 2026-09-17 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5a6"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "folios",
        "guest_id",
        existing_type=sa.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "folios",
        "guest_id",
        existing_type=sa.UUID(as_uuid=True),
        nullable=False,
    )
