"""add MCP system user

Revision ID: 010
Revises: 009
Create Date: 2026-03-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO users (id, email, is_active, subscribe_weekly, created_at)
        VALUES (
            '00000000-0000-0000-0000-000000000002',
            'mcp@system.internal',
            true,
            false,
            NOW()
        )
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM users WHERE id = '00000000-0000-0000-0000-000000000002'
    """)
