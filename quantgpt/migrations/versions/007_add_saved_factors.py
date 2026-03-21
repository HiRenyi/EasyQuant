"""add saved_factors table

Revision ID: 007
Revises: 006
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "saved_factors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("task_id", sa.String(12), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("expression", sa.Text, nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("tags", JSON, nullable=True),
        sa.Column("metrics", JSON, nullable=True),
        sa.Column("backtest_summary", JSON, nullable=True),
        sa.Column("params", JSON, nullable=True),
        sa.Column("report_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("saved_factors")
