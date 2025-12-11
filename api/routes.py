from __future__ import annotations

from datetime import datetime
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from .database import session_dependency
from .models import (
    ChatCreateRequest,
    ChatMessage,
    ChatMessageRequest,
    ChatSession,
    NotificationPolicy,
    NotificationPolicyUpsert,
    ReportDetail,
    ReportFilter,
    ReportSummary,
    ReportStatusUpdate,
    Subscription,
    SubscriptionCreate,
    SubscriptionUpdate,
)
from .notification_constants import NOTIFICATION_TIMEZONE_PRESETS
from .repositories import (
    add_chat_message,
    create_chat_session,
    create_subscription,
    delete_subscription,
    get_report,
    get_notification_policy,
    list_related_reports,
    list_chat_messages,
    list_reports,
    list_subscriptions,
    upsert_notification_policy,
    set_favorite,
    update_report_status,
    update_subscription,
)
from api.vector_search import SearchFilters, get_vector_search_service
from api import db_models
from ingestion.services.chroma_client import ChromaError

router = APIRouter(prefix="/api")

SessionDep = Annotated[Session, Depends(session_dependency)]


async def current_user_id() -> str:
    # TODO: replace with real OAuth2 identity once authentication is wired in
    return "demo-user"


@router.get("/subscriptions", response_model=list[Subscription])
async def list_subscriptions_route(
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> list[Subscription]:
    return list_subscriptions(session, user_id)


@router.post("/subscriptions", response_model=Subscription, status_code=201)
async def create_subscription_route(
    payload: SubscriptionCreate,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> Subscription:
    return create_subscription(session, user_id, payload)


@router.patch("/subscriptions/{subscription_id}", response_model=Subscription)
async def update_subscription_route(
    subscription_id: str,
    payload: SubscriptionUpdate,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> Subscription:
    _ensure_subscription_owner(session, subscription_id, user_id)
    try:
        return update_subscription(session, subscription_id, payload)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail="Subscription not found.") from exc


@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=204,
    response_model=None,
)
async def delete_subscription_route(
    subscription_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> None:
    _ensure_subscription_owner(session, subscription_id, user_id)
    delete_subscription(session, subscription_id)


@router.get("/reports", response_model=list[ReportSummary])
async def list_reports_route(
    session: SessionDep,
    user_id: Annotated[str, Depends(current_user_id)],
    date: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    tickers: list[str] | None = Query(default=None),
    keywords: list[str] | None = Query(default=None),
    urgent_only: bool | None = Query(default=None, alias="urgent_only"),
    sentiment: str | None = Query(
        default=None, pattern="^(positive|neutral|negative)$"
    ),
    favorites_only: bool | None = Query(
        default=None, alias="favorites_only"
    ),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> list[ReportSummary]:
    filter_model = ReportFilter(
        date=datetime.fromisoformat(date) if date else None,
        date_from=datetime.fromisoformat(date_from) if date_from else None,
        date_to=datetime.fromisoformat(date_to) if date_to else None,
        sentiment=sentiment,
        favorites_only=favorites_only,
        status=status,
        search=search,
        tickers=[ticker.upper() for ticker in tickers] if tickers else None,
        keywords=keywords if keywords else None,
        urgent_only=urgent_only,
    )
    return list_reports(session, user_id, filter_model)


@router.get("/search", response_model=list[ReportSummary])
async def search_reports_route(
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    tickers: list[str] | None = Query(default=None),
    keywords: list[str] | None = Query(default=None),
) -> list[ReportSummary]:
    service = get_vector_search_service()
    filters = SearchFilters(
        tickers=[t.upper() for t in tickers] if tickers else None,
        keywords=keywords if keywords else None,
        limit=limit,
    )
    try:
        return service.search_reports(session, query, user_id, filters)
    except ChromaError:
        # 폴백: 기존 리스트 검색(간단 텍스트 매칭)
        filter_model = ReportFilter(
            search=query,
            tickers=filters.tickers,
            keywords=filters.keywords,
        )
        return list_reports(session, user_id, filter_model)


@router.get("/reports/{insight_id}", response_model=ReportDetail)
async def get_report_route(
    insight_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> ReportDetail:
    try:
        return get_report(session, insight_id, user_id)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail="Report not found.") from exc


@router.get("/reports/{insight_id}/related", response_model=list[ReportSummary])
async def list_related_reports_route(
    insight_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> list[ReportSummary]:
    try:
        if os.getenv("VECTOR_RELATED_ENABLED", "false").lower() == "true":
            base_snap = session.get(db_models.ReportSnapshot, insight_id)
            if base_snap is None:
                raise NoResultFound
            service = get_vector_search_service()
            try:
                return service.related_reports(session, base_snap, user_id, limit=3)
            except ChromaError:
                # 폴백: 기존 키워드 기반 로직
                pass
        return list_related_reports(session, user_id, insight_id)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail="Report not found.") from exc


@router.patch("/reports/{insight_id}/status", response_model=ReportDetail)
async def update_report_status_route(
    insight_id: str,
    payload: ReportStatusUpdate,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> ReportDetail:
    if payload.status not in {"draft", "published", "hidden"}:
        raise HTTPException(status_code=400, detail="Invalid status value.")
    try:
        return update_report_status(session, insight_id, payload.status, user_id)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail="Report not found.") from exc


@router.put(
    "/reports/{insight_id}/favorite",
    status_code=204,
    response_model=None,
)
async def mark_favorite_route(
    insight_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> None:
    set_favorite(session, user_id, insight_id, True)


@router.delete(
    "/reports/{insight_id}/favorite",
    status_code=204,
    response_model=None,
)
async def unmark_favorite_route(
    insight_id: str,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> None:
    set_favorite(session, user_id, insight_id, False)


@router.post("/chat/sessions", response_model=ChatSession, status_code=201)
async def create_chat_session_route(
    payload: ChatCreateRequest,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> ChatSession:
    try:
        return create_chat_session(session, user_id, payload.insight_id)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail="Report not found.") from exc


@router.get(
    "/chat/sessions/{session_id}/messages",
    response_model=list[ChatMessage],
)
async def list_chat_messages_route(
    session_id: str,
    session: SessionDep,
) -> list[ChatMessage]:
    return list_chat_messages(session, session_id)


@router.post(
    "/chat/sessions/{session_id}/messages",
    response_model=list[ChatMessage],
    status_code=201,
)
async def post_chat_message_route(
    session_id: str,
    payload: ChatMessageRequest,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> list[ChatMessage]:
    _ = user_id
    try:
        return add_chat_message(session, session_id, "user", payload.content)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail="Chat session not found.") from exc


@router.get("/notifications/policy", response_model=NotificationPolicy)
async def get_notification_policy_route(
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> NotificationPolicy:
    return get_notification_policy(session, user_id)


@router.put("/notifications/policy", response_model=NotificationPolicy)
async def upsert_notification_policy_route(
    payload: NotificationPolicyUpsert,
    user_id: Annotated[str, Depends(current_user_id)],
    session: SessionDep,
) -> NotificationPolicy:
    return upsert_notification_policy(session, user_id, payload)


@router.get("/notifications/timezones", response_model=list[str])
async def list_notification_timezones_route() -> list[str]:
    return NOTIFICATION_TIMEZONE_PRESETS


def _ensure_subscription_owner(
    session: Session, subscription_id: str, user_id: str
) -> None:
    subs = list_subscriptions(session, user_id)
    if not any(sub.subscription_id == subscription_id for sub in subs):
        raise HTTPException(status_code=404, detail="Subscription not found.")


# ===== WebSocket Chat Endpoint =====


@router.websocket("/chat/ws/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    session: SessionDep,
):
    """WebSocket endpoint for real-time chat.

    Protocol:
        Client -> Server: {"type": "message", "content": "..."}
        Server -> Client: {"type": "chunk", "content": "..."}
                         {"type": "done", "message_id": "..."}
                         {"type": "error", "detail": "..."}
    """
    from api.chat_service import ChatServiceError, get_chat_service
    from api.websocket_manager import manager

    await manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") != "message":
                await websocket.send_json(
                    {"type": "error", "code": "invalid_type", "detail": "Invalid message type"}
                )
                continue

            user_message = data.get("content", "").strip()
            if not user_message:
                await websocket.send_json(
                    {"type": "error", "code": "invalid_input", "detail": "Empty message content"}
                )
                continue

            try:
                chat_service = get_chat_service()
                async for chunk in chat_service.handle_message(
                    session, session_id, user_message
                ):
                    await websocket.send_json({"type": "chunk", "content": chunk})

                await websocket.send_json({"type": "done", "message_id": "latest"})

            except ChatServiceError as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": exc.code,
                        "detail": exc.detail,
                        "trace_id": exc.trace_id,
                    }
                )
            except Exception as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "internal_error",
                        "detail": "메시지 처리 중 오류가 발생했습니다.",
                    }
                )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
