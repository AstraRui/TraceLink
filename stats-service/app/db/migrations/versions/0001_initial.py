"""initial clicks table

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clicks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("short_code", sa.String(length=8), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("referer", sa.String(length=2048), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("browser", sa.String(length=64), nullable=True),
        sa.Column("os", sa.String(length=64), nullable=True),
        sa.Column("device_type", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Aggregation queries filter/group on these two columns.
    op.create_index("ix_clicks_short_code", "clicks", ["short_code"])
    op.create_index("ix_clicks_created_at", "clicks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_clicks_created_at", table_name="clicks")
    op.drop_index("ix_clicks_short_code", table_name="clicks")
    op.drop_table("clicks")
