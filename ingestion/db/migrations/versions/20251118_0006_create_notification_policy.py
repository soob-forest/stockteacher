"""create notification_policy table

Revision ID: 20251118_0006
Revises: 20251117_0005_add_more_dummy_raw_articles
Create Date: 2025-11-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251118_0006"
down_revision = "20251117_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_policy",
        sa.Column("policy_id", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("window", sa.String(length=24), nullable=False),
        sa.Column("frequency", sa.String(length=12), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("quiet_hours_start", sa.String(length=5), nullable=True),
        sa.Column("quiet_hours_end", sa.String(length=5), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_notification_policy_user"),
    )
    op.create_index(
        "ix_notification_policy_user_id", "notification_policy", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_notification_policy_user_id", table_name="notification_policy")
    op.drop_table("notification_policy")
