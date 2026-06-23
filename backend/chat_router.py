import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.auth.middleware import get_current_user
from backend.auth.auth_models import Conversation, Message

router = APIRouter(prefix="/chat", tags=["chat"])

BACKEND_URL = "http://127.0.0.1:8000"


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str

    class Config:
        from_attributes = True


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Chat"


class AppendMessageRequest(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class UpdateTitleRequest(BaseModel):
    title: str


# ── Helper ─────────────────────────────────────────────────────────────────────

def _fmt_dt(dt: datetime) -> str:
    """Format a datetime to ISO-8601 string."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _get_conversation_or_403(
    conversation_id: str,
    user: dict,
    db: Session,
) -> Conversation:
    """Fetch conversation and verify ownership; raise 403/404 on failure."""
    conv = db.query(Conversation).filter(
        Conversation.id == uuid.UUID(conversation_id),
        Conversation.is_deleted == False,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if str(conv.user_id) != user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return conv


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(
    body: CreateConversationRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new conversation for the authenticated user."""
    now = datetime.now(timezone.utc)
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user["user_id"]),
        title=body.title or "New Chat",
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationOut(
        id=str(conv.id),
        title=conv.title,
        created_at=_fmt_dt(conv.created_at),
        updated_at=_fmt_dt(conv.updated_at),
    )


@router.get("/conversations", response_model=List[ConversationOut])
def list_conversations(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all non-deleted conversations for the authenticated user, newest first."""
    convs = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == uuid.UUID(user["user_id"]),
            Conversation.is_deleted == False,
        )
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [
        ConversationOut(
            id=str(c.id),
            title=c.title,
            created_at=_fmt_dt(c.created_at),
            updated_at=_fmt_dt(c.updated_at),
        )
        for c in convs
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single conversation (ownership enforced)."""
    conv = _get_conversation_or_403(conversation_id, user, db)
    return ConversationOut(
        id=str(conv.id),
        title=conv.title,
        created_at=_fmt_dt(conv.created_at),
        updated_at=_fmt_dt(conv.updated_at),
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def update_conversation_title(
    conversation_id: str,
    body: UpdateTitleRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the title of a conversation."""
    conv = _get_conversation_or_403(conversation_id, user, db)
    conv.title = body.title
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conv)
    return ConversationOut(
        id=str(conv.id),
        title=conv.title,
        created_at=_fmt_dt(conv.created_at),
        updated_at=_fmt_dt(conv.updated_at),
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def soft_delete_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a conversation (sets is_deleted=True). Record stays in DB."""
    conv = _get_conversation_or_403(conversation_id, user, db)
    conv.is_deleted = True
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageOut])
def get_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all messages for a conversation, ordered chronologically."""
    # Verify ownership first
    _get_conversation_or_403(conversation_id, user, db)
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == uuid.UUID(conversation_id))
        .order_by(Message.created_at.asc())
        .all()
    )
    return [
        MessageOut(
            id=str(m.id),
            conversation_id=str(m.conversation_id),
            role=m.role,
            content=m.content,
            created_at=_fmt_dt(m.created_at),
        )
        for m in msgs
    ]


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=201)
def append_message(
    conversation_id: str,
    body: AppendMessageRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Append a single message to a conversation and bump the conversation's updated_at."""
    conv = _get_conversation_or_403(conversation_id, user, db)

    if body.role not in ("user", "assistant"):
        raise HTTPException(status_code=422, detail="role must be 'user' or 'assistant'")

    now = datetime.now(timezone.utc)
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        role=body.role,
        content=body.content,
        created_at=now,
    )
    db.add(msg)

    # Bump the conversation's updated_at so the sidebar sorts correctly
    conv.updated_at = now
    db.commit()
    db.refresh(msg)

    return MessageOut(
        id=str(msg.id),
        conversation_id=str(msg.conversation_id),
        role=msg.role,
        content=msg.content,
        created_at=_fmt_dt(msg.created_at),
    )
