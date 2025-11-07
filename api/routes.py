from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from .database import session_dependency
from .models import (
    ChatCreateRequest,
    ChatMessage,
    ChatMessageRequest,
    ChatSession,
    ReportDetail,
    ReportFilter,
    ReportSummary,
    Subscription,
    SubscriptionCreate,
    SubscriptionUpdate,
)
from .repositories import (
    add_chat_message,
    create_chat_session,
    create_subscription,
    delete_subscription,
    get_report,
    list_chat_messages,
    list_reports,
    list_subscriptions,
    set_favorite,
    update_subscription,
)

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
    sentiment: str | None = Query(
        default=None, pattern="^(positive|neutral|negative)$"
    ),
    favorites_only: bool | None = Query(
        default=None, alias="favorites_only"
    ),
    search: str | None = Query(default=None),
) -> list[ReportSummary]:
    filter_model = ReportFilter(
        date=datetime.fromisoformat(date) if date else None,
        sentiment=sentiment,
        favorites_only=favorites_only,
        search=search,
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


def _ensure_subscription_owner(
    session: Session, subscription_id: str, user_id: str
) -> None:
    subs = list_subscriptions(session, user_id)
    if not any(sub.subscription_id == subscription_id for sub in subs):
        raise HTTPException(status_code=404, detail="Subscription not found.")
