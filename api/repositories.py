from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import and_, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from . import db_models
from .models import (
    ChatMessage,
    ChatSession,
    ReportDetail,
    ReportFilter,
    ReportSummary,
    Subscription,
    SubscriptionCreate,
    SubscriptionUpdate,
)


def list_subscriptions(session: Session, user_id: str) -> list[Subscription]:
    rows = session.scalars(
        select(db_models.StockSubscription)
        .where(db_models.StockSubscription.user_id == user_id)
        .order_by(db_models.StockSubscription.created_at.desc())
    ).all()
    return [to_subscription(row) for row in rows]


def create_subscription(
    session: Session, user_id: str, payload: SubscriptionCreate
) -> Subscription:
    subscription = db_models.StockSubscription(
        user_id=user_id,
        ticker=payload.ticker.upper(),
        alert_window=payload.alert_window,
        status="Active" if payload.ticker.isalpha() else "PendingVerification",
    )
    session.add(subscription)
    session.flush()
    return to_subscription(subscription)


def update_subscription(
    session: Session, subscription_id: str, payload: SubscriptionUpdate
) -> Subscription:
    subscription = session.get(db_models.StockSubscription, subscription_id)
    if subscription is None:
        raise NoResultFound
    subscription.alert_window = payload.alert_window
    session.flush()
    return to_subscription(subscription)


def delete_subscription(session: Session, subscription_id: str) -> None:
    subscription = session.get(db_models.StockSubscription, subscription_id)
    if subscription:
        session.delete(subscription)
        session.flush()


def list_reports(
    session: Session, user_id: str, filter_: ReportFilter
) -> list[ReportSummary]:
    stmt = select(db_models.ReportSnapshot).order_by(
        db_models.ReportSnapshot.published_at.desc()
    )

    if filter_.favorites_only:
        stmt = stmt.join(
            db_models.FavoriteReport,
            and_(
                db_models.FavoriteReport.insight_id
                == db_models.ReportSnapshot.insight_id,
                db_models.FavoriteReport.user_id == user_id,
            ),
        )
    else:
        stmt = stmt.outerjoin(
            db_models.FavoriteReport,
            and_(
                db_models.FavoriteReport.insight_id
                == db_models.ReportSnapshot.insight_id,
                db_models.FavoriteReport.user_id == user_id,
            ),
        )

    if filter_.date:
        start = filter_.date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
        stmt = stmt.where(
            db_models.ReportSnapshot.published_at.between(start, end)
        )

    if filter_.sentiment:
        stmt = stmt.where(
            sentiment_bucket_clause(
                filter_.sentiment, db_models.ReportSnapshot.sentiment_score
            )
        )

    rows = session.scalars(stmt).unique().all()

    if filter_.search:
        term = filter_.search.lower()
        rows = [
            row
            for row in rows
            if term in row.ticker.lower()
            or term in row.headline.lower()
            or any(term in tag.lower() for tag in (row.tags or []))
        ]

    favorites = {
        fav.insight_id
        for fav in session.scalars(
            select(db_models.FavoriteReport.insight_id).where(
                db_models.FavoriteReport.user_id == user_id
            )
        )
    }

    return [
        to_report_summary(row, row.insight_id in favorites)
        for row in rows
    ]


def get_report(session: Session, insight_id: str, user_id: str) -> ReportDetail:
    report = session.get(db_models.ReportSnapshot, insight_id)
    if report is None:
        raise NoResultFound
    is_favorite = session.scalar(
        select(db_models.FavoriteReport)
        .where(db_models.FavoriteReport.user_id == user_id)
        .where(db_models.FavoriteReport.insight_id == insight_id)
    )
    return to_report_detail(report, is_favorite is not None)


def set_favorite(
    session: Session, user_id: str, insight_id: str, enable: bool
) -> None:
    existing = session.scalar(
        select(db_models.FavoriteReport)
        .where(db_models.FavoriteReport.user_id == user_id)
        .where(db_models.FavoriteReport.insight_id == insight_id)
    )
    if enable:
        if existing is None:
            session.add(
                db_models.FavoriteReport(user_id=user_id, insight_id=insight_id)
            )
    else:
        if existing is not None:
            session.delete(existing)
    session.flush()


def create_chat_session(
    session: Session, user_id: str, insight_id: str
) -> ChatSession:
    chat = db_models.ChatSession(user_id=user_id, insight_id=insight_id)
    session.add(chat)
    session.flush()

    report = session.get(db_models.ReportSnapshot, insight_id)
    if report:
        system_message = db_models.ChatMessage(
            session_id=chat.session_id,
            sender="system",
            content=f"리포트 요약: {report.summary_text}",
        )
        session.add(system_message)
        session.flush()

    return to_chat_session(chat)


def list_chat_messages(session: Session, session_id: str) -> list[ChatMessage]:
    rows = session.scalars(
        select(db_models.ChatMessage)
        .where(db_models.ChatMessage.session_id == session_id)
        .order_by(db_models.ChatMessage.created_at.asc())
    ).all()
    return [to_chat_message(row) for row in rows]


def add_chat_message(
    session: Session, session_id: str, sender: str, content: str
) -> list[ChatMessage]:
    chat_session = session.get(db_models.ChatSession, session_id)
    if chat_session is None:
        raise NoResultFound

    message = db_models.ChatMessage(
        session_id=session_id, sender=sender, content=content
    )
    session.add(message)
    chat_session.status = "Conversing"
    chat_session.updated_at = datetime.utcnow()
    session.flush()

    # NOTE: Hardcoded agent reply removed - now handled by WebSocket streaming
    # if sender == "user":
    #     _append_agent_reply(session, chat_session, content)

    return list_chat_messages(session, session_id)


def _append_agent_reply(
    session: Session, chat_session: db_models.ChatSession, prompt: str
) -> None:
    report = session.get(db_models.ReportSnapshot, chat_session.insight_id)
    summary = report.summary_text if report else ""
    reply_text = (
        "요약 기반 응답: "
        f"{summary[:180]}... "
        f"질문 '{prompt[:80]}'에 대한 기본 설명입니다."
    )
    reply = db_models.ChatMessage(
        session_id=chat_session.session_id, sender="agent", content=reply_text
    )
    session.add(reply)
    chat_session.updated_at = datetime.utcnow()
    session.flush()


def sentiment_bucket_clause(bucket: str, score_column) -> Iterable:
    if bucket == "positive":
        return score_column > 0.2
    if bucket == "negative":
        return score_column < -0.2
    return and_(score_column >= -0.2, score_column <= 0.2)


def to_subscription(row: db_models.StockSubscription) -> Subscription:
    return Subscription.model_validate(
        {
            "subscription_id": row.subscription_id,
            "user_id": row.user_id,
            "ticker": row.ticker,
            "alert_window": row.alert_window,
            "status": row.status,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


def to_report_summary(
    row: db_models.ReportSnapshot, favorite: bool
) -> ReportSummary:
    return ReportSummary.model_validate(
        {
            "insight_id": row.insight_id,
            "ticker": row.ticker,
            "published_at": row.published_at,
            "sentiment_score": row.sentiment_score,
            "headline": row.headline,
            "tags": row.tags or [],
            "favorite": favorite,
        }
    )


def to_report_detail(
    row: db_models.ReportSnapshot, favorite: bool
) -> ReportDetail:
    return ReportDetail.model_validate(
        {
            **to_report_summary(row, favorite).model_dump(),
            "summary_text": row.summary_text,
            "anomaly_score": row.anomaly_score,
            "keywords": row.keywords or [],
            "source_refs": row.source_refs or [],
            "attachments": row.attachments or [],
        }
    )


def to_chat_session(row: db_models.ChatSession) -> ChatSession:
    return ChatSession.model_validate(
        {
            "session_id": row.session_id,
            "insight_id": row.insight_id,
            "user_id": row.user_id,
            "status": row.status,
            "started_at": row.started_at,
            "updated_at": row.updated_at,
        }
    )


def to_chat_message(row: db_models.ChatMessage) -> ChatMessage:
    return ChatMessage.model_validate(
        {
            "message_id": row.message_id,
            "session_id": row.session_id,
            "sender": row.sender,
            "content": row.content,
            "created_at": row.created_at,
        }
    )
