"""update chk_min_floors constraint: number_of_floors >= 1 -> >= 0

Revision ID: d8b0e07e4d0a
Revises: 8252633d3707
Create Date: 2026-07-23 12:55:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d8b0e07e4d0a"
down_revision: Union[str, Sequence[str], None] = "8252633d3707"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("chk_min_floors", "properties", type_="check")
    op.create_check_constraint(
        "chk_min_floors",
        "properties",
        "number_of_floors >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("chk_min_floors", "properties", type_="check")
    op.create_check_constraint(
        "chk_min_floors",
        "properties",
        "number_of_floors >= 1",
    )
