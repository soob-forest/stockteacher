"""Domain DTOs for ingestion pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class RawArticleDTO(BaseModel):
    """Normalized representation of a raw article item."""

    ticker: str = Field(..., description="대상 종목 티커(대문자)")
    source: str = Field(..., description="커넥터 소스 식별자(e.g., news_api)")
    source_type: str = Field(..., description="소스 유형(e.g., news, sns, press)")
    title: str
    body: str
    url: HttpUrl
    collected_at: datetime
    published_at: Optional[datetime] = None
    language: Optional[str] = None
    fingerprint: str = Field(..., description="중복 방지를 위한 해시")

