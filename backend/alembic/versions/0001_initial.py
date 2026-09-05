"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-09-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("google_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "links",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("target_url", sa.Text, nullable=False),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_custom_alias", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_links_code", "links", ["code"])
    op.create_table(
        "clicks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("link_id", sa.Integer, sa.ForeignKey("links.id"), nullable=False),
        sa.Column("clicked_at", sa.DateTime, nullable=False),
        sa.Column("referrer", sa.String(512), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
    )


def downgrade():
    op.drop_table("clicks")
    op.drop_index("ix_links_code", table_name="links")
    op.drop_table("links")
    op.drop_table("users")
