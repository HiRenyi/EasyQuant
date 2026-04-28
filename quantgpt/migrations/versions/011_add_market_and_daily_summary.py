"""add market column + daily_summaries table

Revision ID: 011
Revises: 010
Create Date: 2026-03-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add market column to sessions, saved_factors, featured_factors
    for table in ("sessions", "saved_factors", "featured_factors"):
        op.add_column(table, sa.Column("market", sa.String(20), server_default="a_share", nullable=False))

    # Create daily_summaries table
    op.create_table(
        "daily_summaries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("market", sa.String(20), server_default="a_share", nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_daily_summaries_date_market", "daily_summaries", ["date", "market"], unique=True)


def downgrade() -> None:
    op.drop_table("daily_summaries")
    for table in ("sessions", "saved_factors", "featured_factors"):
        op.drop_column(table, "market")
