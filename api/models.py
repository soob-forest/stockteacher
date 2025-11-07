from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AlertWindow = Literal["intraday", "daily_open", "daily_close", "weekly"]
SubscriptionStatus = Literal["PendingVerification", "Active", "Suspended"]
SentimentBucket = Literal["positive", "neutral", "negative"]
ChatStatus = Literal["Initiated", "Conversing", "Completed", "Handover"]
ChatSender = Literal["user", "agent", "system"]


class Subscription(BaseModel):
    subscription_id: str
    user_id: str
    ticker: str
    alert_window: AlertWindow
    status: SubscriptionStatus
    created_at: datetime
    updated_at: datetime


class SubscriptionCreate(BaseModel):
    ticker: str
    alert_window: AlertWindow


class SubscriptionUpdate(BaseModel):
    alert_window: AlertWindow


class ReportSummary(BaseModel):
    insight_id: str
    ticker: str
    published_at: datetime
    sentiment_score: float
    headline: str
    tags: list[str] = Field(default_factory=list)
    favorite: bool = False


class ReportDetail(ReportSummary):
    summary_text: str
    anomaly_score: float
    keywords: list[str] = Field(default_factory=list)
    source_refs: list[dict[str, str]] = Field(default_factory=list)
    attachments: list[dict[str, str]] = Field(default_factory=list)


class ReportFilter(BaseModel):
    date: datetime | None = None
    sentiment: SentimentBucket | None = None
    favorites_only: bool | None = None
    search: str | None = None


class ChatSession(BaseModel):
    session_id: str
    insight_id: str
    user_id: str
    status: ChatStatus
    started_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    message_id: str
    session_id: str
    sender: ChatSender
    content: str
    created_at: datetime


class ChatCreateRequest(BaseModel):
    insight_id: str


class ChatMessageRequest(BaseModel):
    content: str
