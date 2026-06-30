"""initial links table

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
        "links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("short_code", sa.String(length=8), nullable=False),
        sa.Column("original_url", sa.String(length=2048), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Unique index on the public short code: enforces no two links share a code
    # and gives O(log n) lookups on the redirect hot path.
    op.create_index("ix_links_short_code", "links", ["short_code"], unique=True)
    op.create_index("ix_links_owner_id", "links", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_links_owner_id", table_name="links")
    op.drop_index("ix_links_short_code", table_name="links")
    op.drop_table("links")
