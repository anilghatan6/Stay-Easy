"""must_change_password column added

Revision ID: cccab3fed9fd
Revises: d1ae55913336
Create Date: 2026-08-09 14:18:08.582356

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cccab3fed9fd'
down_revision: Union[str, Sequence[str], None] = 'd1ae55913336'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'guests',
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'users',
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'must_change_password')
    op.drop_column('guests', 'must_change_password')
