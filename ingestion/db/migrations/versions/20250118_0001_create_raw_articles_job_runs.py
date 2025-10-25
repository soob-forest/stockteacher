"""Create raw_articles and job_runs tables"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20250118_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_articles",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("sentiment_raw", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("fingerprint", name="uq_raw_articles_fingerprint"),
    )
    op.create_index(
        "ix_raw_articles_ticker_collected",
        "raw_articles",
        ["ticker", "collected_at"],
        unique=False,
    )

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("task_name", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_job_runs_stage_status", "job_runs", ["stage", "status"], unique=False)
    op.create_index("ix_job_runs_trace", "job_runs", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_job_runs_trace", table_name="job_runs")
    op.drop_index("ix_job_runs_stage_status", table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_index("ix_raw_articles_ticker_collected", table_name="raw_articles")
    op.drop_table("raw_articles")
