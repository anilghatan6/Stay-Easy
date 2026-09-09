"""add user_id to staffs

Revision ID: c1d2e3f4a5b6
Revises: a2b3c4d5e6f7
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add user_id column as nullable
    op.add_column('staffs', sa.Column(
        'user_id',
        sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    ))

    # Step 2: Backfill user_id by matching staffs.email = users.email
    op.execute("""
        UPDATE staffs
        SET user_id = users.id
        FROM users
        WHERE staffs.email = users.email
    """)

    # Step 3: Set NOT NULL constraint
    op.alter_column('staffs', 'user_id', nullable=False)

    # Step 4: Add FK constraint and index
    op.create_foreign_key(
        'fk_staffs_user_id_users',
        'staffs', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_index(op.f('ix_staffs_user_id'), 'staffs', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_staffs_user_id'), table_name='staffs')
    op.drop_constraint('fk_staffs_user_id_users', 'staffs', type_='foreignkey')
    op.drop_column('staffs', 'user_id')
