"""DTO/스키마: 분석 입력/출력 정의.

Pydantic v2 기반의 명확한 스키마로 LLM 입/출력을 정규화한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, ValidationInfo, field_validator


class InputArticle(BaseModel):
    """LLM 분석 입력용 기사 항목."""

    title: str = Field(..., max_length=512)
    body: str = Field(...)
    url: HttpUrl
    language: Optional[str] = Field(default=None, max_length=8)
    published_at: Optional[datetime] = None

    @field_validator("title", "body")
    @classmethod
    def _strip(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("빈 문자열은 허용되지 않습니다.")
        return s


class AnalysisInput(BaseModel):
    """LLM 호출에 필요한 입력 컨테이너."""

    ticker: str = Field(..., description="대상 종목 티커(대문자)")
    locale: str = Field("ko_KR", description="프롬프트 로케일")
    items: List[InputArticle] = Field(default_factory=list, description="분석 대상 기사 목록")
    max_chars: int = Field(5000, ge=500, le=100_000, description="LLM 입력으로 사용할 최대 문자 수(요약/청크 기준)")

    @field_validator("ticker")
    @classmethod
    def _ticker_upper(cls, v: str) -> str:
        s = v.strip().upper()
        if not s:
            raise ValueError("ticker는 공백일 수 없습니다.")
        return s

    @field_validator("items")
    @classmethod
    def _non_empty_items(cls, v: List[InputArticle]) -> List[InputArticle]:
        if len(v) == 0:
            raise ValueError("분석 대상 기사가 최소 1개 필요합니다.")
        return v


class AnomalyItem(BaseModel):
    """이상 이벤트 항목."""

    label: str = Field(..., max_length=64)
    description: str = Field(..., max_length=512)
    score: float = Field(..., ge=0.0, le=1.0, description="이상 점수(0~1)")

    @field_validator("label", "description")
    @classmethod
    def _strip_nonempty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("필드는 공백일 수 없습니다.")
        return s


class AnalysisResult(BaseModel):
    """LLM 분석 결과 표준 스키마."""

    ticker: str
    summary_text: str = Field(..., max_length=4000)
    keywords: List[str] = Field(default_factory=list, description="핵심 키워드")
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    anomalies: List[AnomalyItem] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # LLM 메타
    llm_model: str
    llm_tokens_prompt: int = Field(..., ge=0)
    llm_tokens_completion: int = Field(..., ge=0)
    llm_cost: float = Field(..., ge=0.0)

    @field_validator("ticker")
    @classmethod
    def _ticker_upper_out(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("summary_text")
    @classmethod
    def _summary_trim(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("summary_text는 공백일 수 없습니다.")
        return s

    @field_validator("keywords")
    @classmethod
    def _keywords_cleanup(cls, v: List[str], info: ValidationInfo) -> List[str]:  # noqa: ARG002
        cleaned: List[str] = []
        seen: set[str] = set()
        for kw in v:
            s = (kw or "").strip()
            if not s or s.lower() in seen:
                continue
            cleaned.append(s)
            seen.add(s.lower())
            if len(cleaned) >= 10:
                break
        return cleaned
