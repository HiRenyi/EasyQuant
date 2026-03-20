"""add iteration fields to tasks

Revision ID: 002
Revises: 001
Create Date: 2026-03-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("task_type", sa.String(20), nullable=True, server_default="backtest"))
    op.add_column("tasks", sa.Column("parent_task_id", sa.String(12), sa.ForeignKey("tasks.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "parent_task_id")
    op.drop_column("tasks", "task_type")
