"""Add additional dummy raw_articles for local development."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20251117_0005"
down_revision = "20251117_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    base_time = datetime.now(timezone.utc)

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

    rows = [
        {
            "id": uuid.uuid4(),
            "ticker": "TSLA",
            "source": "news_api",
            "source_type": "news",
            "title": "Dummy TSLA article: battery supply concerns resurface",
            "body": "This is a dummy TSLA article body used for local ingestion testing.",
            "url": "https://example.com/tsla-dummy-article",
            "fingerprint": "dev_tsla_dummy_article_1",
            "collected_at": base_time - timedelta(hours=7),
            "published_at": base_time - timedelta(hours=8),
            "language": "en",
            "sentiment_raw": None,
        },
        {
            "id": uuid.uuid4(),
            "ticker": "MSFT",
            "source": "news_api",
            "source_type": "news",
            "title": "Dummy MSFT article: cloud and AI copilots extend growth runway",
            "body": "This is a dummy MSFT article body used for local ingestion testing.",
            "url": "https://example.com/msft-dummy-article",
            "fingerprint": "dev_msft_dummy_article_1",
            "collected_at": base_time - timedelta(hours=13),
            "published_at": base_time - timedelta(hours=14),
            "language": "en",
            "sentiment_raw": None,
        },
        {
            "id": uuid.uuid4(),
            "ticker": "NVDA",
            "source": "news_api",
            "source_type": "news",
            "title": "Dummy NVDA article: hyperscaler AI capex supports GPU demand",
            "body": "This is a dummy NVDA article body used for local ingestion testing.",
            "url": "https://example.com/nvda-dummy-article",
            "fingerprint": "dev_nvda_dummy_article_1",
            "collected_at": base_time - timedelta(days=1, hours=1),
            "published_at": base_time - timedelta(days=1, hours=2),
            "language": "en",
            "sentiment_raw": None,
        },
    ]

    conn.execute(sa.insert(raw_articles), rows)


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "DELETE FROM raw_articles "
            "WHERE fingerprint IN ("
            "'dev_tsla_dummy_article_1',"
            "'dev_msft_dummy_article_1',"
            "'dev_nvda_dummy_article_1'"
            ")"
        )
    )

