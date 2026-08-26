"""add shift to staffs

Revision ID: b7e8f9a0c1d2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-25 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e8f9a0c1d2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the ShiftType enum type
    shift_enum = sa.Enum('MORNING', 'EVENING', 'NIGHT', name='shifttype', create_type=False)
    shift_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('staffs', sa.Column(
        'shift',
        sa.Enum('MORNING', 'EVENING', 'NIGHT', name='shifttype', create_type=False),
        nullable=False,
        server_default='MORNING',
    ))
    op.create_index(op.f('ix_staffs_shift'), 'staffs', ['shift'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_staffs_shift'), table_name='staffs')
    op.drop_column('staffs', 'shift')
    sa.Enum(name='shifttype').drop(op.get_bind(), checkfirst=True)
