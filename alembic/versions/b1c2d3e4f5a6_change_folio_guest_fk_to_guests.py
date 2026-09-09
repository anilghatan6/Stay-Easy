"""change folio guest_id FK from users to guests

Revision ID: b1c2d3e4f5a6
Revises: 176823ba0308
Create Date: 2026-09-03 16:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "176823ba0308"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing FK constraint on folios.guest_id -> users.id
    op.drop_constraint("folios_guest_id_fkey", "folios", type_="foreignkey")

    # Create new FK constraint: folios.guest_id -> guests.id
    op.create_foreign_key(
        "folios_guest_id_fkey",
        "folios",
        "guests",
        ["guest_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Drop the guests FK
    op.drop_constraint("folios_guest_id_fkey", "folios", type_="foreignkey")

    # Restore the users FK
    op.create_foreign_key(
        "folios_guest_id_fkey",
        "folios",
        "users",
        ["guest_id"],
        ["id"],
        ondelete="RESTRICT",
    )
