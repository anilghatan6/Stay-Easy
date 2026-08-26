"""add housekeeping mobile tables

Revision ID: f1e2d3c4b5a6
Revises: b7e8f9a0c1d2
Create Date: 2026-08-25 20:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, Sequence[str], None] = 'b7e8f9a0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Define all ENUM types explicitly
    maintenance_category = postgresql.ENUM(
        'PLUMBING', 'ELECTRICAL', 'HVAC', 'FURNITURE', 'APPLIANCE',
        'FLOORING', 'PAINTING', 'LOCK_SECURITY', 'OTHER',
        name='maintenancecategory'
    )
    task_priority = postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='taskpriority')
    task_status = postgresql.ENUM('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='taskstatus')
    shift_type = postgresql.ENUM('MORNING', 'EVENING', 'NIGHT', name='shifttype')
    swap_status = postgresql.ENUM('PENDING', 'ACCEPTED', 'REJECTED', name='swapstatus')
    leave_type = postgresql.ENUM(
        'SICK_LEAVE', 'PERSONAL_LEAVE', 'VACATION', 'UNPAID_LEAVE', 'OTHER',
        name='leavetype'
    )
    leave_status = postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', name='leavestatus')

    # 2. Create types safely (checkfirst ensures it won't crash if already present)
    bind = op.get_bind()
    maintenance_category.create(bind, checkfirst=True)
    task_priority.create(bind, checkfirst=True)
    task_status.create(bind, checkfirst=True)
    shift_type.create(bind, checkfirst=True)
    swap_status.create(bind, checkfirst=True)
    leave_type.create(bind, checkfirst=True)
    leave_status.create(bind, checkfirst=True)

    # 3. Create tables using create_type=False for column references
    op.create_table(
        'maintenance_reports',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('property_id', sa.Uuid(), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False),
        sa.Column('room_id', sa.Uuid(), sa.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('staff_id', sa.Uuid(), sa.ForeignKey('staffs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', postgresql.ENUM('PLUMBING', 'ELECTRICAL', 'HVAC', 'FURNITURE', 'APPLIANCE', 'FLOORING', 'PAINTING', 'LOCK_SECURITY', 'OTHER', name='maintenancecategory', create_type=False), nullable=False),
        sa.Column('priority', postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='taskpriority', create_type=False), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('photos', sa.JSON(), nullable=True),
        sa.Column('status', postgresql.ENUM('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='taskstatus', create_type=False), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_maintenance_reports_property_id', 'maintenance_reports', ['property_id'])
    op.create_index('ix_maintenance_reports_room_id', 'maintenance_reports', ['room_id'])
    op.create_index('ix_maintenance_reports_staff_id', 'maintenance_reports', ['staff_id'])

    op.create_table(
        'shift_swap_requests',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('property_id', sa.Uuid(), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requester_staff_id', sa.Uuid(), sa.ForeignKey('staffs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requester_shift', postgresql.ENUM('MORNING', 'EVENING', 'NIGHT', name='shifttype', create_type=False), nullable=False),
        sa.Column('target_staff_id', sa.Uuid(), sa.ForeignKey('staffs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_shift', postgresql.ENUM('MORNING', 'EVENING', 'NIGHT', name='shifttype', create_type=False), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'ACCEPTED', 'REJECTED', name='swapstatus', create_type=False), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_shift_swap_requests_requester_staff_id', 'shift_swap_requests', ['requester_staff_id'])
    op.create_index('ix_shift_swap_requests_target_staff_id', 'shift_swap_requests', ['target_staff_id'])

    op.create_table(
        'leave_requests',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('property_id', sa.Uuid(), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False),
        sa.Column('staff_id', sa.Uuid(), sa.ForeignKey('staffs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('leave_type', postgresql.ENUM('SICK_LEAVE', 'PERSONAL_LEAVE', 'VACATION', 'UNPAID_LEAVE', 'OTHER', name='leavetype', create_type=False), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(length=1000), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', name='leavestatus', create_type=False), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_leave_requests_staff_id', 'leave_requests', ['staff_id'])

    op.create_table(
        'staff_schedules',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('property_id', sa.Uuid(), sa.ForeignKey('properties.id', ondelete='CASCADE'), nullable=False),
        sa.Column('staff_id', sa.Uuid(), sa.ForeignKey('staffs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shift_date', sa.Date(), nullable=False),
        sa.Column('shift_type', postgresql.ENUM('MORNING', 'EVENING', 'NIGHT', name='shifttype', create_type=False), nullable=False),
        sa.Column('check_in_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('check_out_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_staff_schedules_staff_id', 'staff_schedules', ['staff_id'])
    op.create_index('ix_staff_schedules_property_id', 'staff_schedules', ['property_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('staff_schedules')
    op.drop_table('leave_requests')
    op.drop_table('shift_swap_requests')
    op.drop_table('maintenance_reports')

    bind = op.get_bind()
    postgresql.ENUM(name='leavestatus').drop(bind, checkfirst=True)
    postgresql.ENUM(name='leavetype').drop(bind, checkfirst=True)
    postgresql.ENUM(name='swapstatus').drop(bind, checkfirst=True)
    postgresql.ENUM(name='shifttype').drop(bind, checkfirst=True)
    postgresql.ENUM(name='taskstatus').drop(bind, checkfirst=True)
    postgresql.ENUM(name='taskpriority').drop(bind, checkfirst=True)
    postgresql.ENUM(name='maintenancecategory').drop(bind, checkfirst=True)