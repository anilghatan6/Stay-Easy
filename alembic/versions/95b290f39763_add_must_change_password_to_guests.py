"""add must_change_password to guests and users

Revision ID: add_password_flag
Revises: <YOUR_PREVIOUS_REVISION_ID>
Create Date: 2026-08-23 ...
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'add_password_flag'
down_revision: Union[str, Sequence[str], None] = 'a1fe580dbc7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Safely add the column with a server default so existing rows don't fail
    op.add_column('guests', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.text('false')))

def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
    op.drop_column('guests', 'must_change_password')