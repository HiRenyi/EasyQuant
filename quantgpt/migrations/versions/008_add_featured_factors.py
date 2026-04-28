"""add featured_factors table for factor wall

Revision ID: 008
Revises: 007
Create Date: 2026-03-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "featured_factors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expression", sa.Text, nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metrics", JSON, nullable=True),
        sa.Column("backtest_summary", JSON, nullable=True),
        sa.Column("params", JSON, nullable=True),
        sa.Column("report_url", sa.String(500), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="submission"),  # 'official' | 'submission'
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),  # 'pending' | 'approved' | 'rejected'
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("featured_factors")
