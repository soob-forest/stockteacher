"""Configuration models for the ingestion service."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, List, Optional, Set, Tuple

from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    SecretStr,
    ValidationError,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class CollectionSchedule(BaseModel):
    """Represents a periodic collection job configuration."""

    ticker: str = Field(..., description="대상 종목 티커 (대문자).")
    source: str = Field(..., description="데이터 소스 식별자 (예: news_api).")
    interval_minutes: PositiveInt = Field(..., description="수집 주기 (분 단위).")
    enabled: bool = Field(True, description="스케줄 사용 여부.")

    @field_validator("ticker")
    @classmethod
    def _ticker_to_upper(cls, value: str) -> str:
        ticker = value.strip().upper()
        if not ticker:
            raise ValueError("ticker는 공백일 수 없습니다.")
        return ticker

    @field_validator("source")
    @classmethod
    def _normalize_source(cls, value: str) -> str:
        source = value.strip()
        if not source:
            raise ValueError("source는 공백일 수 없습니다.")
        return source


class Settings(BaseSettings):
    """Ingestion용 환경 설정."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    redis_url: str = Field(..., alias="INGESTION_REDIS_URL", description="Celery 브로커/백엔드 Redis DSN.")
    news_api_key: Optional[SecretStr] = Field(None, alias="NEWS_API_KEY", description="뉴스 API 인증 키.")
    news_api_endpoint: str = Field(
        "https://newsapi.org/v2/everything",
        alias="NEWS_API_ENDPOINT",
        description="News API 엔드포인트",
    )
    news_api_timeout_seconds: PositiveInt = Field(5, alias="NEWS_API_TIMEOUT_SECONDS", description="News API 타임아웃(초)")
    news_api_max_retries: PositiveInt = Field(2, alias="NEWS_API_MAX_RETRIES", description="News API 최대 재시도")
    news_api_page_size: PositiveInt = Field(20, alias="NEWS_API_PAGE_SIZE", description="News API 페이지 크기(≤100)")
    news_api_lang: str = Field("ko", alias="NEWS_API_LANG", description="News API 언어 필터")
    news_api_sort_by: str = Field("publishedAt", alias="NEWS_API_SORT_BY", description="정렬 기준")
    postgres_dsn: str = Field(..., alias="POSTGRES_DSN", description="PostgreSQL 연결 문자열.")
    local_storage_root: str = Field(
        "./var/storage",
        alias="LOCAL_STORAGE_ROOT",
        description="원문/스냅샷 로컬 저장소 루트 경로.",
    )
    default_locale: str = Field("ko_KR", alias="DEFAULT_LOCALE", description="기본 로케일.")
    structlog_level: str = Field("INFO", alias="STRUCTLOG_LEVEL", description="구조화 로그 레벨.")
    log_json: bool = Field(False, alias="LOG_JSON", description="로그를 JSON 형식으로 출력할지 여부.")
    collection_schedules: List[CollectionSchedule] = Field(
        default_factory=list,
        alias="COLLECTION_SCHEDULES",
        description="JSON 배열 혹은 객체 리스트 형태의 수집 스케줄.",
    )
    dedup_redis_ttl_seconds: PositiveInt = Field(86_400, alias="DEDUP_REDIS_TTL_SECONDS", description="중복 캐시 TTL.")
    celery_worker_concurrency: PositiveInt = Field(
        4,
        alias="CELERY_WORKER_CONCURRENCY",
        description="Celery 워커 동시 실행 수.",
    )
    celery_task_soft_time_limit: PositiveInt = Field(
        300,
        alias="CELERY_TASK_SOFT_TIME_LIMIT",
        description="Celery 태스크 소프트 타임아웃 (초).",
    )

    @field_validator("collection_schedules", mode="before")
    @classmethod
    def _parse_collection_schedules(cls, value: Any) -> List[Any]:
        if value in (None, "", []):
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("COLLECTION_SCHEDULES는 JSON 배열이어야 합니다.") from exc
            return parsed
        if isinstance(value, list):
            return value
        raise ValueError("COLLECTION_SCHEDULES는 리스트 형태여야 합니다.")

    @field_validator("collection_schedules")
    @classmethod
    def _validate_unique_schedule(cls, value: List[CollectionSchedule]) -> List[CollectionSchedule]:
        seen: Set[Tuple[str, str]] = set()
        for schedule in value:
            key = (schedule.ticker, schedule.source)
            if key in seen:
                raise ValueError(f"중복된 스케줄 항목이 존재합니다: {schedule.ticker}/{schedule.source}")
            seen.add(key)
        return value

    @field_validator("local_storage_root")
    @classmethod
    def _validate_local_root(cls, value: str) -> str:
        root = value.strip()
        if not root:
            raise ValueError("LOCAL_STORAGE_ROOT는 공백일 수 없습니다.")
        return root

    @field_validator("postgres_dsn")
    @classmethod
    def _validate_postgres_dsn(cls, value: str) -> str:
        if "://" not in value:
            raise ValueError("POSTGRES_DSN은 유효한 DSN 문자열이어야 합니다.")
        return value

    @field_validator("news_api_page_size")
    @classmethod
    def _validate_page_size(cls, v: int) -> int:
        if v > 100:
            raise ValueError("NEWS_API_PAGE_SIZE는 100 이하여야 합니다.")
        return v


@lru_cache()
def get_settings() -> Settings:
    """환경 변수를 기준으로 Settings 인스턴스를 반환한다."""
    try:
        return Settings()
    except ValidationError as exc:
        raise RuntimeError(f"환경 변수 검증에 실패했습니다: {exc}") from exc


def reset_settings_cache() -> None:
    """Settings LRU 캐시를 초기화한다 (테스트 용도)."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
