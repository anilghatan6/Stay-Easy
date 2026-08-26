"""add allow_pay_on_arrival and advance percentage fields to properties

Revision ID: a1b2c3d4e5f6
Revises: d5e6f7a8b9c0
Create Date: 2026-08-24 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "dd044c9c571e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "properties",
        sa.Column(
            "allow_pay_on_arrival",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "properties",
        sa.Column(
            "min_advance_percentage",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("10"),
        ),
    )
    op.add_column(
        "properties",
        sa.Column(
            "max_advance_percentage",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("50"),
        ),
    )


def downgrade() -> None:
    op.drop_column("properties", "max_advance_percentage")
    op.drop_column("properties", "min_advance_percentage")
    op.drop_column("properties", "allow_pay_on_arrival")
