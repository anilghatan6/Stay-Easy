"""stub for missing migration dd044c9c571e

Revision ID: dd044c9c571e
Revises: d5e6f7a8b9c0
Create Date: 2026-08-24 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "dd044c9c571e"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
