"""add subscription, feature_flags, announcements tables

Revision ID: e9522e8927d6
Revises: 6e8df93141b1
Create Date: 2026-09-21 13:41:40.936266

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e9522e8927d6'
down_revision: Union[str, Sequence[str], None] = '6e8df93141b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── subscription_plans ───
    op.create_table(
        'subscription_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(50), unique=True, nullable=False),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_properties', sa.Integer, nullable=False, server_default='1'),
        sa.Column('max_staff', sa.Integer, nullable=False, server_default='5'),
        sa.Column('features', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── tenant_subscriptions ───
    op.create_table(
        'tenant_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'tenant_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            'plan_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('subscription_plans.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
        sa.Column('billing_cycle', sa.String(10), nullable=False, server_default='MONTHLY'),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── feature_flags ───
    op.create_table(
        'feature_flags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('key', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_enabled', sa.Boolean, nullable=False, server_default='false'),
        sa.Column(
            'created_by',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── announcements ───
    op.create_table(
        'announcements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('priority', sa.String(20), nullable=False, server_default='INFO'),
        sa.Column('target', sa.String(10), nullable=False, server_default='ALL'),
        sa.Column('target_admin_ids', postgresql.JSONB(), nullable=True),
        sa.Column('send_email', sa.Boolean, nullable=False, server_default='false'),
        sa.Column(
            'created_by',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('announcements')
    op.drop_table('feature_flags')
    op.drop_table('tenant_subscriptions')
    op.drop_table('subscription_plans')
