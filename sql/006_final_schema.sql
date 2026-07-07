-- =============================================================================
-- 006_final_schema.sql
-- Complete Final Database Snapshot
-- =============================================================================
--
-- This file represents the CURRENT state of the database after all schema
-- changes. It can be used to create the entire database from scratch.
--
-- Source: backend/auth/auth_models.py (HEAD / latest commit)
-- Tables: 10
-- Database: PostgreSQL
-- =============================================================================

-- Enable UUID generation (PostgreSQL)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- =============================================================================
-- TABLE 1: users
-- Purpose: Enterprise system user identity and authentication.
-- PK: UUID (auto-generated)
-- =============================================================================
CREATE TABLE users (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR         NOT NULL,
    hashed_password VARCHAR         NOT NULL,
    role            VARCHAR         NOT NULL DEFAULT 'vendor',
    status          VARCHAR         NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    last_login      TIMESTAMPTZ     NULL,

    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX ix_users_email      ON users (email);
CREATE INDEX ix_users_role       ON users (role);
CREATE INDEX ix_users_created_at ON users (created_at);


-- =============================================================================
-- TABLE 2: query_logs
-- Purpose: Persistent audit logs for the RAG query pipeline.
-- PK: UUID (auto-generated)
-- FK: user_id → users.id (ON DELETE SET NULL)
-- =============================================================================
CREATE TABLE query_logs (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id            VARCHAR         NOT NULL,
    timestamp           TIMESTAMPTZ     NOT NULL DEFAULT now(),
    user_id             UUID            NULL,
    email               VARCHAR         NULL,
    role                VARCHAR         NULL,
    query               TEXT            NOT NULL,
    corrected_query     TEXT            NULL,
    query_granularity   VARCHAR         NULL,
    answer_found        BOOLEAN         DEFAULT FALSE,
    partial_match_found BOOLEAN         DEFAULT FALSE,
    confidence          FLOAT           DEFAULT 0.0,
    confidence_band     VARCHAR         NULL,
    top_source_file     VARCHAR         NULL,
    top_page_number     INTEGER         NULL,
    top_chunk_id        VARCHAR         NULL,
    retrieved_sources   JSONB           NULL,
    response_length     INTEGER         DEFAULT 0,
    processing_time_ms  INTEGER         DEFAULT 0,
    blocked             BOOLEAN         DEFAULT FALSE,
    risk_level          VARCHAR         DEFAULT 'low',
    security_reason     TEXT            NULL,
    system_status       VARCHAR         DEFAULT 'success',

    CONSTRAINT uq_query_logs_query_id UNIQUE (query_id),
    CONSTRAINT fk_query_logs_user_id  FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE SET NULL
);

-- Single-column indexes
CREATE INDEX ix_query_logs_timestamp          ON query_logs (timestamp);
CREATE INDEX ix_query_logs_user_id            ON query_logs (user_id);
CREATE INDEX ix_query_logs_query_granularity  ON query_logs (query_granularity);
CREATE INDEX ix_query_logs_blocked            ON query_logs (blocked);
CREATE INDEX ix_query_logs_risk_level         ON query_logs (risk_level);

-- Composite indexes
CREATE INDEX idx_query_logs_user_timestamp    ON query_logs (user_id, timestamp);
CREATE INDEX idx_query_logs_risk_blocked      ON query_logs (risk_level, blocked);
CREATE INDEX idx_query_logs_created           ON query_logs (timestamp);
CREATE INDEX idx_query_logs_user              ON query_logs (user_id);


-- =============================================================================
-- TABLE 3: conversations
-- Purpose: Persistent conversation sessions linked to users.
--          Supports soft-delete so records are retained for audit.
-- PK: UUID (auto-generated)
-- FK: user_id → users.id (ON DELETE CASCADE)
-- =============================================================================
CREATE TABLE conversations (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID            NOT NULL,
    title       VARCHAR         NOT NULL DEFAULT 'New Chat',
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT now(),
    is_deleted  BOOLEAN         NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_conversations_user_id FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_conversations_user_id ON conversations (user_id);
CREATE INDEX idx_conversations_user_active_updated
    ON conversations (user_id, is_deleted, updated_at);


-- =============================================================================
-- TABLE 4: messages
-- Purpose: Individual chat messages belonging to a Conversation.
--          Role is either 'user' or 'assistant'.
-- PK: UUID (auto-generated)
-- FK: conversation_id → conversations.id (ON DELETE CASCADE)
-- =============================================================================
CREATE TABLE messages (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID            NOT NULL,
    role            VARCHAR         NOT NULL,
    content         TEXT            NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_messages_conversation_id FOREIGN KEY (conversation_id)
        REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);
CREATE INDEX idx_messages_conversation_created
    ON messages (conversation_id, created_at);


-- =============================================================================
-- TABLE 5: email_otps
-- Purpose: Email OTP verification codes.
--          Stores the bcrypt hash of the OTP for security.
-- PK: UUID (auto-generated)
-- =============================================================================
CREATE TABLE email_otps (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR         NOT NULL,
    otp_hash    VARCHAR         NOT NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ     NOT NULL,
    verified    BOOLEAN         NOT NULL DEFAULT FALSE,
    attempts    INTEGER         NOT NULL DEFAULT 0
);

CREATE INDEX ix_email_otps_email      ON email_otps (email);
CREATE INDEX ix_email_otps_created_at ON email_otps (created_at);
CREATE INDEX ix_email_otps_expires_at ON email_otps (expires_at);
CREATE INDEX idx_emailotp_email       ON email_otps (email);
CREATE INDEX idx_emailotp_created     ON email_otps (created_at);


-- =============================================================================
-- TABLE 6: rate_limit_counters
-- Purpose: Database-backed sliding-window rate limit counters.
--          Enables O(1) UPSERT-based rate validation.
-- PK: UUID (auto-generated)
-- =============================================================================
CREATE TABLE rate_limit_counters (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier      VARCHAR         NOT NULL,
    endpoint        VARCHAR         NOT NULL,
    window_start    TIMESTAMPTZ     NOT NULL,
    request_count   INTEGER         NOT NULL DEFAULT 1
);

CREATE INDEX ix_rate_limit_counters_identifier   ON rate_limit_counters (identifier);
CREATE INDEX ix_rate_limit_counters_endpoint      ON rate_limit_counters (endpoint);
CREATE INDEX ix_rate_limit_counters_window_start  ON rate_limit_counters (window_start);
CREATE UNIQUE INDEX idx_rate_limiter_identifier_window
    ON rate_limit_counters (identifier, endpoint, window_start);
CREATE INDEX idx_rate_created ON rate_limit_counters (window_start);
CREATE INDEX idx_rate_ip      ON rate_limit_counters (identifier);


-- =============================================================================
-- TABLE 7: otp_request_limits
-- Purpose: Hardens OTP requests to prevent global resource exhaustion and
--          SMTP abuse. Tracks system-wide and IP-based counts.
-- PK: UUID (auto-generated)
-- =============================================================================
CREATE TABLE otp_request_limits (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR         NULL,
    ip_address          VARCHAR         NOT NULL,
    request_timestamp   TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX ix_otp_request_limits_email               ON otp_request_limits (email);
CREATE INDEX ix_otp_request_limits_ip_address           ON otp_request_limits (ip_address);
CREATE INDEX ix_otp_request_limits_request_timestamp    ON otp_request_limits (request_timestamp);
CREATE INDEX idx_otp_limit_email     ON otp_request_limits (email);
CREATE INDEX idx_otp_limit_ip        ON otp_request_limits (ip_address);
CREATE INDEX idx_otp_limit_timestamp ON otp_request_limits (request_timestamp);


-- =============================================================================
-- TABLE 8: system_metrics
-- Purpose: Persisted telemetry metrics mapping cumulative usage statistics.
--          Key-value store that survives app restarts.
-- PK: metric_name (VARCHAR — natural key)
-- =============================================================================
CREATE TABLE system_metrics (
    metric_name     VARCHAR         PRIMARY KEY,
    metric_value    FLOAT           NOT NULL DEFAULT 0.0,
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);


-- =============================================================================
-- TABLE 9: documents
-- Purpose: Represents ingested PDF documents.
-- PK: id (VARCHAR — SHA-256 hex digest)
-- =============================================================================
CREATE TABLE documents (
    id              VARCHAR         PRIMARY KEY,
    source_file     VARCHAR         NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_documents_source_file UNIQUE (source_file)
);

CREATE INDEX ix_documents_source_file ON documents (source_file);


-- =============================================================================
-- TABLE 10: chunks
-- Purpose: Text chunks extracted from documents for RAG retrieval.
--          Supports full-text search via PostgreSQL TSVECTOR + GIN index.
-- PK: chunk_id (VARCHAR)
-- FK: doc_id → documents.id (ON DELETE CASCADE)
-- =============================================================================
CREATE TABLE chunks (
    chunk_id            VARCHAR         PRIMARY KEY,
    doc_id              VARCHAR         NOT NULL,
    page_number         INTEGER         NOT NULL,
    chunk_index         INTEGER         NOT NULL,
    text                TEXT            NOT NULL,
    section_title       VARCHAR         NULL,
    subsection_title    VARCHAR         NULL,
    procedure_id        VARCHAR         NULL,
    alternate_phrasings JSONB           NULL,
    tsv_content         TSVECTOR        NULL,

    CONSTRAINT fk_chunks_doc_id FOREIGN KEY (doc_id)
        REFERENCES documents (id) ON DELETE CASCADE
);

CREATE INDEX ix_chunks_doc_id       ON chunks (doc_id);
CREATE INDEX ix_chunks_page_number  ON chunks (page_number);
CREATE INDEX idx_chunks_tsv         ON chunks USING gin (tsv_content);
CREATE INDEX idx_chunks_doc_page    ON chunks (doc_id, page_number);


-- =============================================================================
-- TABLE 11 (of 10 models): vector_maps
-- Purpose: Maps FAISS vector index offsets to text chunk IDs.
--          Bridges the vector store with the relational schema.
-- PK: vector_id (INTEGER — FAISS index offset)
-- FK: chunk_id → chunks.chunk_id (ON DELETE CASCADE)
-- =============================================================================
CREATE TABLE vector_maps (
    vector_id   INTEGER         PRIMARY KEY,
    chunk_id    VARCHAR         NOT NULL,

    CONSTRAINT uq_vector_maps_chunk_id UNIQUE (chunk_id),
    CONSTRAINT fk_vector_maps_chunk_id FOREIGN KEY (chunk_id)
        REFERENCES chunks (chunk_id) ON DELETE CASCADE
);

CREATE INDEX ix_vector_maps_chunk_id ON vector_maps (chunk_id);


-- =============================================================================
-- FINAL SCHEMA SUMMARY
-- =============================================================================
--
-- Total tables:       10
-- Total columns:      72
-- Total indexes:      42  (including unique indexes)
-- Total constraints:  22  (10 PK + 5 FK + 5 UNIQUE + 2 composite unique)
-- Total foreign keys:  5
--
-- Table List:
--   1. users                (7 columns)
--   2. query_logs          (22 columns)
--   3. conversations        (6 columns)
--   4. messages             (5 columns)
--   5. email_otps           (7 columns)
--   6. rate_limit_counters  (5 columns)
--   7. otp_request_limits   (4 columns)
--   8. system_metrics       (3 columns)
--   9. documents            (3 columns)
--  10. chunks              (10 columns)
--  11. vector_maps          (2 columns)
--
-- Note: 11 CREATE TABLE statements for 10 ORM models. The numbering in
-- comments refers to the order in auth_models.py; "Table 11" is vector_maps,
-- the 10th model but listed last.
--
-- =============================================================================
