"""add indexes for room filters and property amenities

Revision ID: 625a9b743fd5
Revises: c1d2e3f4a5b6
Create Date: 2026-09-03 15:27:17.291159

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '625a9b743fd5'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_index(
        "ix_rooms_type_bed_rate",
        "rooms",
        ["room_type_id", "bed_type_id", "base_rate"],
        unique=False,
    )
    op.create_index(
        "ix_properties_amenities_gin",
        "properties",
        ["system_amenity_ids"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_properties_amenities_gin", table_name="properties")
    op.drop_index("ix_rooms_type_bed_rate", table_name="rooms")
