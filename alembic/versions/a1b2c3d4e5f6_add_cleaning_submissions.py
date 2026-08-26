"""add cleaning submissions table and awaiting_inspection status

Revision ID: a1b2c3d4e5f6
Revises: f1e2d3c4b5a6
Create Date: 2026-08-25 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f1e2d3c4b5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add AWAITING_INSPECTION to existing taskstatus enum
    task_status = postgresql.ENUM(
        'PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'AWAITING_INSPECTION',
        name='taskstatus'
    )
    bind = op.get_bind()
    task_status.create(bind, checkfirst=True)

    # Add the new enum value if it doesn't exist
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'AWAITING_INSPECTION'")

    # 2. Create cleaningsubmissionstatus enum
    submission_status = postgresql.ENUM(
        'PENDING_REVIEW', 'APPROVED', 'REJECTED',
        name='cleaningsubmissionstatus'
    )
    submission_status.create(bind, checkfirst=True)

    # 3. Create cleaning_submissions table
    op.create_table(
        'cleaning_submissions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('task_id', sa.Uuid(), sa.ForeignKey('housekeeping_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('property_id', sa.Uuid(), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False),
        sa.Column('room_id', sa.Uuid(), sa.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('staff_id', sa.Uuid(), sa.ForeignKey('staffs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('checklist_items', postgresql.JSONB(), server_default='{"items": []}', nullable=False),
        sa.Column('before_images', postgresql.JSONB(), server_default='{"gallery": []}', nullable=False),
        sa.Column('after_images', postgresql.JSONB(), server_default='{"gallery": []}', nullable=False),
        sa.Column('suppliers_used', postgresql.JSONB(), server_default='{"suppliers": []}', nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING_REVIEW', 'APPROVED', 'REJECTED', name='cleaningsubmissionstatus', create_type=False), nullable=False, server_default='PENDING_REVIEW'),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column('reviewed_by_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_cleaning_submissions_task_id', 'cleaning_submissions', ['task_id'])
    op.create_index('ix_cleaning_submissions_property_id', 'cleaning_submissions', ['property_id'])
    op.create_index('ix_cleaning_submissions_room_id', 'cleaning_submissions', ['room_id'])
    op.create_index('ix_cleaning_submissions_staff_id', 'cleaning_submissions', ['staff_id'])
    op.create_index('ix_cleaning_submissions_status', 'cleaning_submissions', ['status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('cleaning_submissions')
    bind = op.get_bind()
    postgresql.ENUM(name='cleaningsubmissionstatus').drop(bind, checkfirst=True)
