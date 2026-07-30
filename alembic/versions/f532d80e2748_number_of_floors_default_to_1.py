"""number of floors default to 1

Revision ID: f532d80e2748
Revises: 14d437f84180
Create Date: 2026-07-30 12:05:22.927771

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f532d80e2748'
down_revision: Union[str, Sequence[str], None] = '14d437f84180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely without data loss."""
    # 1. Update any existing records where floors are 0 or NULL to 1
    op.execute(
        "UPDATE properties SET number_of_floors = 1 WHERE number_of_floors < 1 OR number_of_floors IS NULL"
    )
    
    # 2. Drop the old >= 0 constraint
    op.drop_constraint("chk_min_floors", "properties", type_="check")
    
    # 3. Apply the new >= 1 constraint safely
    op.create_check_constraint(
        "chk_min_floors",
        "properties",
        "number_of_floors >= 1",
    )
    
    # 4. Apply your other intended model modifications safely
    op.alter_column('rooms', 'base_rate',
               existing_type=sa.NUMERIC(precision=10, scale=2),
               nullable=False)
    
    # Check if these indexes already exist in your DB; if they crash, you can comment them out.
    # op.create_index(op.f('ix_rooms_room_name'), 'rooms', ['room_name'], unique=False)
    # op.create_index('ix_rooms_status', 'rooms', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # op.drop_index('ix_rooms_status', table_name='rooms')
    # op.drop_index(op.f('ix_rooms_room_name'), table_name='rooms')
    op.alter_column('rooms', 'base_rate',
               existing_type=sa.NUMERIC(precision=10, scale=2),
               nullable=True)
    op.drop_constraint("chk_min_floors", "properties", type_="check")
    op.create_check_constraint(
        "chk_min_floors",
        "properties",
        "number_of_floors >= 0",
    )
