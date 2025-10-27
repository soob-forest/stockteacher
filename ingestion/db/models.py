"""SQLAlchemy models for ingestion data."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Index,
    Integer,
    Float,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    """Base class for ORM models."""


class TimestampMixin:
    """Adds created_at/updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class JobStage(str, Enum):
    COLLECT = "collect"
    ANALYZE = "analyze"
    DELIVER = "deliver"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY = "retry"


class RawArticle(TimestampMixin, Base):
    """Raw article collected from external sources."""

    __tablename__ = "raw_articles"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_raw_articles_fingerprint"),
        Index("ix_raw_articles_ticker_collected", "ticker", "collected_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    language: Mapped[str | None] = mapped_column(String(8))
    sentiment_raw: Mapped[str | None] = mapped_column(String(32))


class JobRun(TimestampMixin, Base):
    """Represents a single job execution."""

    __tablename__ = "job_runs"
    __table_args__ = (
        Index("ix_job_runs_stage_status", "stage", "status"),
        Index("ix_job_runs_trace", "trace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    stage: Mapped[JobStage] = mapped_column(
        SAEnum(JobStage, name="job_stage", native_enum=False, length=16),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status", native_enum=False, length=16),
        nullable=False,
        default=JobStatus.PENDING,
    )
    ticker: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[str | None] = mapped_column(String(50))
    task_name: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(512))
    trace_id: Mapped[str | None] = mapped_column(String(64))


class ProcessedInsight(TimestampMixin, Base):
    """LLM로 생성된 분석 결과를 저장."""

    __tablename__ = "processed_insights"
    __table_args__ = (
        Index("ix_processed_insights_ticker_generated", "ticker", "generated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    anomalies: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    source_refs: Mapped[list[dict] | None] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # LLM meta
    llm_model: Mapped[str] = mapped_column(String(64), nullable=False)
    llm_tokens_prompt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_tokens_completion: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
