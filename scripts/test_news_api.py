"""Quick NewsAPI connector smoke test.

Usage:
  uv run -- python scripts/test_news_api.py -t AAPL -n 5 --attempts 2

Reads configuration from .env via pydantic settings. Requires NEWS_API_KEY.
Prints fetched count and a few top items (title + URL).
"""

from __future__ import annotations

import argparse
import sys
from typing import List
import os

from ingestion.connectors.news_api import NewsAPIConnector
from ingestion.connectors.base import TransientError, PermanentError
from ingestion.settings import get_settings


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NewsAPI smoke test")
    parser.add_argument("-t", "--ticker", default="AAPL", help="Ticker symbol (default: AAPL)")
    parser.add_argument("-n", "--top", type=int, default=5, help="Print top N items (default: 5)")
    parser.add_argument("--attempts", type=int, default=2, help="Max attempts for fetch (default: 2)")
    args = parser.parse_args(argv)

    # Ensure minimal required envs for settings to load
    os.environ.setdefault("INGESTION_REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("POSTGRES_DSN", "sqlite:///./var/dev.db")
    os.environ.setdefault("LOCAL_STORAGE_ROOT", "./var/storage")

    cfg = get_settings()
    print(
        "Config:",
        {
            "endpoint": cfg.news_api_endpoint,
            "lang": cfg.news_api_lang,
            "page_size": int(cfg.news_api_page_size),
            "timeout_s": int(cfg.news_api_timeout_seconds),
        },
    )

    connector = NewsAPIConnector()
    try:
        items = connector.fetch(args.ticker, max_attempts=args.attempts)
    except PermanentError as exc:
        print(f"Permanent error: {exc}")
        return 2
    except TransientError as exc:
        print(f"Transient error: {exc}")
        return 3
    except Exception as exc:  # unexpected
        print(f"Unexpected error: {exc}")
        return 4

    print(f"Fetched {len(items)} items for {args.ticker}.")
    for idx, it in enumerate(items[: args.top], start=1):
        print(f"{idx}. [{it.ticker}] {it.title[:120]}\n   {it.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
