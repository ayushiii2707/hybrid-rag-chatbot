import uuid
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Index, Text, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from backend.database.db import Base

class User(Base):
    """
    User model representing enterprise system identity.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)  # UNIQUE INDEX on email
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="vendor", nullable=False, index=True)  # INDEX on role
    status = Column(String, default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)  # INDEX on created_at
    last_login = Column(DateTime(timezone=True), nullable=True)


class QueryLog(Base):
    """
    QueryLog model representing persistent audit logs.
    """
    __tablename__ = "query_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(String, unique=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)  # INDEX on timestamp
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # INDEX on user_id
    email = Column(String, nullable=True)
    role = Column(String, nullable=True)
    query = Column(Text, nullable=False)
    corrected_query = Column(Text, nullable=True)
    query_granularity = Column(String, nullable=True, index=True)  # INDEX on query_granularity
    answer_found = Column(Boolean, default=False)
    partial_match_found = Column(Boolean, default=False)
    confidence = Column(Float, default=0.0)
    confidence_band = Column(String, nullable=True)
    top_source_file = Column(String, nullable=True)
    top_page_number = Column(Integer, nullable=True)
    top_chunk_id = Column(String, nullable=True)
    retrieved_sources = Column(JSONB, nullable=True)
    response_length = Column(Integer, default=0)
    processing_time_ms = Column(Integer, default=0)
    blocked = Column(Boolean, default=False, index=True)  # INDEX on blocked
    risk_level = Column(String, default="low", index=True)  # INDEX on risk_level
    security_reason = Column(Text, nullable=True)
    system_status = Column(String, default="success")

    # Composite indexes and other table properties
    __table_args__ = (
        Index("idx_query_logs_user_timestamp", "user_id", "timestamp"),
        Index("idx_query_logs_risk_blocked", "risk_level", "blocked"),
    )


class Conversation(Base):
    """
    Persistent conversation session linked to a user.
    Supports soft-delete so records are retained for audit.
    """
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String, nullable=False, default="New Chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        # Fast sidebar query: fetch all active convs for a user sorted by recency
        Index("idx_conversations_user_active_updated", "user_id", "is_deleted", "updated_at"),
    )


class Message(Base):
    """
    Individual chat message belonging to a Conversation.
    Role is either 'user' or 'assistant'.
    """
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String, nullable=False)   # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # Ordered message retrieval for a conversation
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
    )


class EmailOTP(Base):
    """
    Model representing email OTP verification codes.
    Stores the bcrypt hash of the OTP for security.
    """
    __tablename__ = "email_otps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, index=True)
    otp_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    verified = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
