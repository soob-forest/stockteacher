# News Integration Plan (On Hold)

## Current Status
- NewsAPI connector (HTTP path, pagination, retry handling) is in production with pytest-httpx coverage and a local smoke script (`scripts/test_news_api.py`).
- RSS connector has been dropped from the MVP. No runtime code depends on `SNS_FEED_URLS`, and related docs/tests/scripts have been removed.

## Deferred Goals
- No additional news sources will ship for the MVP. RSS or alternative feeds will be reconsidered only after the NewsAPI path proves stable in production.

## Backlog Items to Revisit Later
- Evaluate additional providers or RSS feeds (including required parser/HTTP retry helpers) once product requirements justify the operational cost.
- Expand contract tests with real provider fixtures if/when multi-source support returns.

## Recommended Next Watchpoints
- Monitor NewsAPI error rates, quota usage, and latency via existing observability hooks.
- Document a Decision Log entry before reintroducing any new data source to capture scope, cost, and testing expectations.

## Rollback / Contingency
- If NewsAPI usage must be suspended, disable the corresponding collection schedules and rely on manual ingestion until a new source is approved.
