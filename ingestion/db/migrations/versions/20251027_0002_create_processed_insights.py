"""Create processed_insights table"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251027_0002"
down_revision = "20250118_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_insights",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=False),
        sa.Column("anomalies", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("llm_model", sa.String(length=64), nullable=False),
        sa.Column("llm_tokens_prompt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_tokens_completion", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(
        "ix_processed_insights_ticker_generated",
        "processed_insights",
        ["ticker", "generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_processed_insights_ticker_generated", table_name="processed_insights")
    op.drop_table("processed_insights")

