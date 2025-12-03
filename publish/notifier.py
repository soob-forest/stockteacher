from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db_models import NotificationPolicy as NotificationPolicyRow
from api.db_models import ReportSnapshot, StockSubscription
from api.models import DEFAULT_NOTIFICATION_POLICY, NotificationPolicy
from api.repositories import to_notification_policy

URGENT_ANOMALY_THRESHOLD = 0.7
URGENT_SENTIMENT_THRESHOLD = -0.6


@dataclass(frozen=True)
class DispatchedNotification:
    user_id: str
    channels: list[str]
    ticker: str
    insight_id: str
    reason: str


def is_urgent_snapshot(snapshot: ReportSnapshot) -> tuple[bool, str | None]:
    if snapshot.anomaly_score is not None and snapshot.anomaly_score >= URGENT_ANOMALY_THRESHOLD:
        return True, "anomaly"
    if snapshot.sentiment_score is not None and snapshot.sentiment_score <= URGENT_SENTIMENT_THRESHOLD:
        return True, "sentiment"
    return False, None


def dispatch_urgent_notifications(
    session: Session,
    snapshot: ReportSnapshot,
    *,
    now: datetime | None = None,
) -> list[DispatchedNotification]:
    urgent, reason = is_urgent_snapshot(snapshot)
    if not urgent:
        return []

    recipients = _load_recipients(session, snapshot.ticker)
    dispatched: list[DispatchedNotification] = []
    for user_id, policy in recipients:
        if _is_quiet(policy, now):
            continue
        dispatched.append(
            DispatchedNotification(
                user_id=user_id,
                channels=list(policy.channels),
                ticker=snapshot.ticker,
                insight_id=snapshot.insight_id,
                reason=reason or "unknown",
            )
        )
    return dispatched


def _load_recipients(
    session: Session, ticker: str
) -> list[tuple[str, NotificationPolicy]]:
    subscribers: Iterable[StockSubscription] = session.scalars(
        select(StockSubscription).where(
            StockSubscription.ticker == ticker.upper(),
            StockSubscription.status == "Active",
        )
    )
    result: list[tuple[str, NotificationPolicy]] = []
    for sub in subscribers:
        policy_row = session.scalar(
            select(NotificationPolicyRow).where(
                NotificationPolicyRow.user_id == sub.user_id
            )
        )
        if policy_row is None:
            policy = NotificationPolicy.model_validate(
                {**DEFAULT_NOTIFICATION_POLICY, "user_id": sub.user_id}
            )
        else:
            policy = to_notification_policy(policy_row)
        result.append((sub.user_id, policy))
    return result


def _is_quiet(policy: NotificationPolicy, now: datetime | None) -> bool:
    if not policy.quiet_hours_start or not policy.quiet_hours_end:
        return False

    tz = ZoneInfo(policy.timezone)
    current = (now or datetime.now(timezone.utc)).astimezone(tz).time()
    start = _parse_time(policy.quiet_hours_start)
    end = _parse_time(policy.quiet_hours_end)
    return start <= current < end


def _parse_time(value: str) -> time:
    hour_str, minute_str = value.split(":")
    return time(int(hour_str), int(minute_str))
