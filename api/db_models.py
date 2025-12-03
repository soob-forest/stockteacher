from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class StockSubscription(Base):
    __tablename__ = "stock_subscription"

    subscription_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: _prefixed_id("sub")
    )
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    alert_window: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(24), default="PendingVerification")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )


class ReportSnapshot(Base):
    __tablename__ = "report_snapshot"

    insight_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: _prefixed_id("insight")
    )
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    headline: Mapped[str] = mapped_column(String(512))
    summary_text: Mapped[str] = mapped_column(String(4000))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(12), default="published", server_default="published", index=True)
    sentiment_score: Mapped[float] = mapped_column(Float)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_refs: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    attachments: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)

    favorites: Mapped[list["FavoriteReport"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class FavoriteReport(Base):
    __tablename__ = "favorite_report"
    __table_args__ = (UniqueConstraint("user_id", "insight_id"),)

    favorite_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: _prefixed_id("fav")
    )
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    insight_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("report_snapshot.insight_id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    report: Mapped[ReportSnapshot] = relationship(back_populates="favorites")


class ChatSession(Base):
    __tablename__ = "chat_session"

    session_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: _prefixed_id("chat")
    )
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    insight_id: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(16), default="Initiated")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "chat_message"

    message_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: _prefixed_id("msg")
    )
    session_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("chat_session.session_id", ondelete="CASCADE")
    )
    sender: Mapped[str] = mapped_column(String(8))
    content: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), index=True
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class NotificationPolicy(Base):
    __tablename__ = "notification_policy"
    __table_args__ = (UniqueConstraint("user_id"),)

    policy_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: _prefixed_id("np")
    )
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    timezone: Mapped[str] = mapped_column(String(64))
    window: Mapped[str] = mapped_column(String(24))
    frequency: Mapped[str] = mapped_column(String(12))
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )


def _prefixed_id(prefix: str) -> str:
    from uuid import uuid4

    return f"{prefix}_{uuid4().hex[:12]}"


def seed_reports(session: Session) -> None:
    if session.query(ReportSnapshot).count() > 0:
        return

    now = datetime.now(timezone.utc)
    seeds: Iterable[ReportSnapshot] = [
        ReportSnapshot(
            insight_id="insight_a",
            ticker="AAPL",
            headline="Apple unveils new AI chipset and beats expectations",
            summary_text="Apple introduced a next-generation AI chipset alongside expanding services revenue, lifting analyst expectations for upcoming quarters.",
            published_at=now - timedelta(hours=2),
            status="published",
            sentiment_score=0.42,
            anomaly_score=0.18,
            tags=["ai", "earnings"],
            keywords=["AI chipset", "services revenue", "guidance"],
            source_refs=[
                {
                    "title": "Bloomberg: Apple outlines AI roadmap",
                    "url": "https://example.com/apple-ai",
                }
            ],
            attachments=[],
        ),
        ReportSnapshot(
            insight_id="insight_b",
            ticker="TSLA",
            headline="Tesla slides on renewed battery supply concerns",
            summary_text="Renewed worries about the EV battery supply chain triggered a pullback in Tesla shares as investors reassessed production targets.",
            published_at=now - timedelta(hours=5),
            status="published",
            sentiment_score=-0.35,
            anomaly_score=0.44,
            tags=["supply-chain", "ev"],
            keywords=["battery", "supply chain", "production target"],
            source_refs=[
                {
                    "title": "Reuters: Battery constraints resurface",
                    "url": "https://example.com/tesla-battery",
                }
            ],
            attachments=[],
        ),
    ]
    session.add_all(seeds)
    session.commit()
