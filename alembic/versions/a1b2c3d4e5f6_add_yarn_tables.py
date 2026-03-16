"""add_yarn_tables

Revision ID: a1b2c3d4e5f6
Revises: 7a2b9b6c1088
Create Date: 2026-03-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7a2b9b6c1088'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'yarn_colors',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('color_code', sa.String(20), nullable=False, unique=True),
        sa.Column('opening_stock', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('idx_yarn_colors_code', 'yarn_colors', ['color_code'])

    op.create_table(
        'yarn_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('color_id', sa.Integer(), sa.ForeignKey('yarn_colors.id'), nullable=False),
        sa.Column('transaction_type', sa.String(3), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('idx_yarn_tx_color_id', 'yarn_transactions', ['color_id'])
    op.create_index('idx_yarn_tx_date', 'yarn_transactions', ['date'])
    op.create_index('idx_yarn_tx_project_id', 'yarn_transactions', ['project_id'])


def downgrade() -> None:
    op.drop_table('yarn_transactions')
    op.drop_table('yarn_colors')
