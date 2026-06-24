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
        Index("idx_query_logs_created", "timestamp"),
        Index("idx_query_logs_user", "user_id"),
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True) # Index on created_at for cleanup performance
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    verified = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)

    # Constraint to ensure non-empty hashes and fast retrieval
    __table_args__ = (
        Index("idx_emailotp_email", "email"),
        Index("idx_emailotp_created", "created_at"),
    )


class RateLimitCounter(Base):
    """
    Highly performant, database-backed rate limit counters to track sliding-window request volume.
    Pushes rate validation logic from memory/full scans to O(1) UPSERTs.
    """
    __tablename__ = "rate_limit_counters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identifier = Column(String, nullable=False, index=True) # Holds IP or user_id
    endpoint = Column(String, nullable=False, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    request_count = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("idx_rate_limiter_identifier_window", "identifier", "endpoint", "window_start", unique=True),
        Index("idx_rate_created", "window_start"),
        Index("idx_rate_ip", "identifier"),
    )


class OTPRequestLimit(Base):
    """
    Harden OTP requests table to prevent global resource exhaustion and SMTP abuse.
    Tracks system-wide and IP-based counts.
    """
    __tablename__ = "otp_request_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=True, index=True)
    ip_address = Column(String, nullable=False, index=True)
    request_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("idx_otp_limit_email", "email"),
        Index("idx_otp_limit_ip", "ip_address"),
        Index("idx_otp_limit_timestamp", "request_timestamp"),
    )


class SystemMetric(Base):
    """
    Persisted telemetry metrics mapping cumulative usage statistics.
    Survives app restarts.
    """
    __tablename__ = "system_metrics"

    metric_name = Column(String, primary_key=True)
    metric_value = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

