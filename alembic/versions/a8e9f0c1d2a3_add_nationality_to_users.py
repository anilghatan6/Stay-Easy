"""add nationality to users

Revision ID: add_nationality_users
Revises: c4d5e6f7a8b0
Create Date: 2026-09-22 ...
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'add_nationality_users'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('users', sa.Column('nationality', sa.String(length=100), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'nationality')