"""add sessions table and task.session_id

Revision ID: 004
Revises: 003
Create Date: 2026-03-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.add_column("tasks", sa.Column("session_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_tasks_session_id", "tasks", "sessions", ["session_id"], ["id"])
    op.create_index("ix_tasks_session_id", "tasks", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_session_id", table_name="tasks")
    op.drop_constraint("fk_tasks_session_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "session_id")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
