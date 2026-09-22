"""add geo_location geography column to properties

Revision ID: b3c4d5e6f7a8
Revises: e9522e8927d6
Create Date: 2026-09-22 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'e9522e8927d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure PostGIS extension is available
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Add the geo_location geography column
    op.add_column(
        "properties",
        sa.Column("geo_location", Geography(geometry_type="POINT", srid=4326), nullable=True),
    )

    # Backfill from existing latitude/longitude columns
    op.execute(
        """
        UPDATE properties
        SET geo_location = ST_SetSRID(
            ST_MakePoint(longitude::float, latitude::float), 4326
        )::geography
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    )

    # Create GiST spatial index for fast proximity queries
    op.execute(
        "CREATE INDEX ix_properties_geo_location_gist ON properties USING GIST (geo_location)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_properties_geo_location_gist")
    op.drop_column("properties", "geo_location")
