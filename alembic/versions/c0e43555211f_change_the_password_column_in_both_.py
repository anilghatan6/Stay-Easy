"""change the password column in both guests and users

Revision ID: c0e43555211f
Revises: d4be4e5e74e3
Create Date: 2026-08-04 12:39:36.646944

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c0e43555211f"
down_revision: Union[str, Sequence[str], None] = "d4be4e5e74e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add the column allowing NULL values initially
    op.add_column('guests', sa.Column('hashed_password', sa.String(length=255), nullable=True))
    
    # 2. Backfill existing rows: Copy data from password_hash to hashed_password
    op.execute("UPDATE guests SET hashed_password = password_hash")
    
    # 3. For any legacy guests with no password, assign a dummy string so the constraint doesn't fail
    # op.execute("UPDATE guests SET hashed_password = 'legacy_no_password' WHERE hashed_password IS NULL")
    
    # 4. Now that every row has data, safely enforce the NOT NULL constraint
    op.alter_column('guests', 'hashed_password', nullable=False)
    
    # 5. Safely drop the old column
    op.drop_column('guests', 'password_hash')

    # ⚠️ CRITICAL: Remove any lines here where Alembic tries to drop "spatial_ref_sys" 
    # or drop your "properties" geometric indexes. Delete those drop lines from the script.


def downgrade() -> None:
    # Reverse the exact logic safely
    op.add_column('guests', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.execute("UPDATE guests SET password_hash = hashed_password")
    op.alter_column('guests', 'password_hash', nullable=False)
    op.drop_column('guests', 'hashed_password')
