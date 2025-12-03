from __future__ import annotations

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

AlertWindow = Literal["intraday", "daily_open", "daily_close", "weekly"]
SubscriptionStatus = Literal["PendingVerification", "Active", "Suspended"]
SentimentBucket = Literal["positive", "neutral", "negative"]
ChatStatus = Literal["Initiated", "Conversing", "Completed", "Handover"]
ChatSender = Literal["user", "agent", "system"]
ReportStatus = Literal["draft", "published", "hidden"]
NotificationWindow = Literal["morning_open", "daily_close", "immediate"]
NotificationFrequency = Literal["daily", "weekly"]
NotificationChannel = Literal["email", "web-push"]


DEFAULT_NOTIFICATION_POLICY = {
    "timezone": "Asia/Seoul",
    "window": "daily_close",
    "frequency": "daily",
    "channels": ["email"],
    "quiet_hours_start": None,
    "quiet_hours_end": None,
}


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
    status: ReportStatus
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
    date_from: datetime | None = None
    date_to: datetime | None = None
    sentiment: SentimentBucket | None = None
    favorites_only: bool | None = None
    status: str | None = None
    search: str | None = None
    tickers: list[str] | None = None
    keywords: list[str] | None = None
    urgent_only: bool | None = None


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


class ReportStatusUpdate(BaseModel):
    status: ReportStatus


class NotificationPolicyBase(BaseModel):
    timezone: str
    window: NotificationWindow
    frequency: NotificationFrequency
    channels: list[NotificationChannel] = Field(min_length=1)
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError("Invalid timezone") from exc
        return value

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, value: list[NotificationChannel]) -> list[NotificationChannel]:
        if not value:
            raise ValueError("At least one channel is required.")
        return value

    @model_validator(mode="after")
    def validate_quiet_hours(self):
        if not self.quiet_hours_start and not self.quiet_hours_end:
            return self
        if not self.quiet_hours_start or not self.quiet_hours_end:
            raise ValueError("quiet_hours_start and quiet_hours_end must both be provided.")
        start = _parse_hhmm(self.quiet_hours_start)
        end = _parse_hhmm(self.quiet_hours_end)
        if start >= end:
            raise ValueError("quiet_hours_start must be before quiet_hours_end.")
        return self


class NotificationPolicy(NotificationPolicyBase):
    user_id: str


class NotificationPolicyUpsert(NotificationPolicyBase):
    pass


def _parse_hhmm(value: str):
    hour, minute = value.split(":")
    hour_int = int(hour)
    minute_int = int(minute)
    if hour_int < 0 or hour_int > 23 or minute_int < 0 or minute_int > 59:
        raise ValueError("Time must be in HH:MM 24h format.")
    return (hour_int, minute_int)
