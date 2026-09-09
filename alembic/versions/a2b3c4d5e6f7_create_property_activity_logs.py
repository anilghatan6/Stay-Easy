"""create property_activity_logs table

Revision ID: a2b3c4d5e6f7
Revises: e7f4a9b2c3d1
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'e7f4a9b2c3d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'property_activity_logs',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('property_id', sa.UUID(as_uuid=True), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('staff_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('staff_name', sa.String(255), nullable=False),
        sa.Column('activity_type', sa.String(50), nullable=False, index=True),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('booking_id', sa.UUID(as_uuid=True), sa.ForeignKey('bookings.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('room_id', sa.UUID(as_uuid=True), sa.ForeignKey('rooms.id', ondelete='SET NULL'), nullable=True),
        sa.Column('extra_data', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_property_activity_logs_created_at_desc', 'property_activity_logs', [sa.text('created_at DESC')])


def downgrade() -> None:
    op.drop_index('idx_property_activity_logs_created_at_desc', table_name='property_activity_logs')
    op.drop_table('property_activity_logs')
