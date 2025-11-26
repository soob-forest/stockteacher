"""Seed dummy ingestion data for local development."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20251117_0003"
down_revision = "20251027_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    raw_articles = sa.table(
        "raw_articles",
        sa.column("id", sa.Uuid()),
        sa.column("ticker", sa.String()),
        sa.column("source", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("title", sa.String()),
        sa.column("body", sa.Text()),
        sa.column("url", sa.String()),
        sa.column("fingerprint", sa.String()),
        sa.column("collected_at", sa.DateTime(timezone=True)),
        sa.column("published_at", sa.DateTime(timezone=True)),
        sa.column("language", sa.String()),
        sa.column("sentiment_raw", sa.String()),
    )

    processed_insights = sa.table(
        "processed_insights",
        sa.column("id", sa.Uuid()),
        sa.column("ticker", sa.String()),
        sa.column("summary_text", sa.Text()),
        sa.column("keywords", sa.JSON()),
        sa.column("sentiment_score", sa.Float()),
        sa.column("anomalies", sa.JSON()),
        sa.column("source_refs", sa.JSON()),
        sa.column("generated_at", sa.DateTime(timezone=True)),
        sa.column("llm_model", sa.String()),
        sa.column("llm_tokens_prompt", sa.Integer()),
        sa.column("llm_tokens_completion", sa.Integer()),
        sa.column("llm_cost", sa.Float()),
    )

    article_id = uuid.uuid4()
    insight_id = uuid.uuid4()

    conn.execute(
        sa.insert(raw_articles),
        [
            {
                "id": article_id,
                "ticker": "AAPL",
                "source": "news_api",
                "source_type": "news",
                "title": "Dummy Apple article for local development",
                "body": "This is a dummy article body used for local ingestion/analysis testing.",
                "url": "https://example.com/aapl-dummy-article",
                "fingerprint": "dev_aapl_dummy_article_1",
                "collected_at": now,
                "published_at": now,
                "language": "en",
                "sentiment_raw": None,
            },
        ],
    )

    conn.execute(
        sa.insert(processed_insights),
        [
            {
                "id": insight_id,
                "ticker": "AAPL",
                "summary_text": "Dummy processed insight for AAPL, used to test the web/API pipeline end-to-end.",
                "keywords": ["apple", "dummy", "local-dev"],
                "sentiment_score": 0.15,
                "anomalies": [],
                "source_refs": [
                    {
                        "title": "Dummy Apple article for local development",
                        "url": "https://example.com/aapl-dummy-article",
                    }
                ],
                "generated_at": now,
                "llm_model": "gpt-4o-mini",
                "llm_tokens_prompt": 64,
                "llm_tokens_completion": 32,
                "llm_cost": 0.0003,
            },
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "DELETE FROM processed_insights "
            "WHERE ticker = :ticker AND summary_text LIKE :summary_prefix"
        ),
        {"ticker": "AAPL", "summary_prefix": "Dummy processed insight for AAPL%"},
    )

    conn.execute(
        sa.text(
            "DELETE FROM raw_articles WHERE fingerprint = :fp"
        ),
        {"fp": "dev_aapl_dummy_article_1"},
    )

