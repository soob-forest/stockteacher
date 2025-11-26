"""Add additional dummy processed_insights for local development."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20251117_0004"
down_revision = "20251117_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    base_time = datetime.now(timezone.utc)

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

    rows = [
        {
            "id": uuid.uuid4(),
            "ticker": "TSLA",
            "summary_text": "Dummy TSLA insight: renewed battery supply concerns cause short-term volatility, but long-term demand remains intact.",
            "keywords": ["tesla", "battery", "supply chain"],
            "sentiment_score": -0.25,
            "anomalies": [{"label": "supply_chain", "score": 0.5}],
            "source_refs": [
                {
                    "title": "Dummy TSLA article",
                    "url": "https://example.com/tsla-dummy-article",
                }
            ],
            "generated_at": base_time - timedelta(hours=6),
            "llm_model": "gpt-4o-mini",
            "llm_tokens_prompt": 120,
            "llm_tokens_completion": 60,
            "llm_cost": 0.0006,
        },
        {
            "id": uuid.uuid4(),
            "ticker": "MSFT",
            "summary_text": "Dummy MSFT insight: steady cloud growth and AI copilots drive margin expansion despite FX headwinds.",
            "keywords": ["microsoft", "azure", "copilot"],
            "sentiment_score": 0.35,
            "anomalies": [],
            "source_refs": [
                {
                    "title": "Dummy MSFT article",
                    "url": "https://example.com/msft-dummy-article",
                }
            ],
            "generated_at": base_time - timedelta(hours=12),
            "llm_model": "gpt-4o-mini",
            "llm_tokens_prompt": 110,
            "llm_tokens_completion": 55,
            "llm_cost": 0.00055,
        },
        {
            "id": uuid.uuid4(),
            "ticker": "NVDA",
            "summary_text": "Dummy NVDA insight: hyperscaler AI capex remains elevated, supporting strong GPU demand into next year.",
            "keywords": ["nvidia", "gpu", "ai capex"],
            "sentiment_score": 0.48,
            "anomalies": [{"label": "valuation", "score": 0.3}],
            "source_refs": [
                {
                    "title": "Dummy NVDA article",
                    "url": "https://example.com/nvda-dummy-article",
                }
            ],
            "generated_at": base_time - timedelta(days=1),
            "llm_model": "gpt-4o-mini",
            "llm_tokens_prompt": 130,
            "llm_tokens_completion": 70,
            "llm_cost": 0.0007,
        },
    ]

    conn.execute(sa.insert(processed_insights), rows)


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "DELETE FROM processed_insights "
            "WHERE ticker IN ('TSLA','MSFT','NVDA') "
            "AND summary_text LIKE 'Dummy % insight:%'"
        )
    )
