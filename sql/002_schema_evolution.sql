-- =============================================================================
-- 002_schema_evolution.sql
-- Chronological Schema Changes After Initial Creation
-- =============================================================================
--
-- This file reconstructs every schema change that occurred after the initial
-- database creation (001_initial_schema.sql). Changes are ordered
-- chronologically by commit.
--
-- Source: Git history (git diff between consecutive commits affecting
--         backend/auth/auth_models.py)
--
-- No tables or columns were ever removed during the project's history.
-- All changes are additive.
-- =============================================================================


-- =============================================================================
-- PHASE 2: Commit 35ca000
-- "feat: implement persistent dual-mode OTP flow, fix stuck spinner,
--  and configure CORS origins"
--
-- Added 3 new tables: conversations, messages, email_otps
-- No changes to existing tables (users, query_logs)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- NEW TABLE: conversations
-- Purpose: Persistent conversation sessions linked to users.
--          Supports soft-delete so records are retained for audit.
-- -----------------------------------------------------------------------------
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

-- Single-column index
CREATE INDEX ix_conversations_user_id ON conversations (user_id);

-- Composite index: fast sidebar query for active conversations sorted by recency
CREATE INDEX idx_conversations_user_active_updated
    ON conversations (user_id, is_deleted, updated_at);


-- -----------------------------------------------------------------------------
-- NEW TABLE: messages
-- Purpose: Individual chat messages belonging to a Conversation.
--          Role is either 'user' or 'assistant'.
-- -----------------------------------------------------------------------------
CREATE TABLE messages (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID            NOT NULL,
    role            VARCHAR         NOT NULL,
    content         TEXT            NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_messages_conversation_id FOREIGN KEY (conversation_id)
        REFERENCES conversations (id) ON DELETE CASCADE
);

-- Single-column index
CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

-- Composite index: ordered message retrieval for a conversation
CREATE INDEX idx_messages_conversation_created
    ON messages (conversation_id, created_at);


-- -----------------------------------------------------------------------------
-- NEW TABLE: email_otps
-- Purpose: Email OTP verification codes.
--          Stores the bcrypt hash of the OTP for security.
-- Note: At this phase, created_at did NOT have an index.
--       The __table_args__ composite indexes were not yet defined.
-- -----------------------------------------------------------------------------
CREATE TABLE email_otps (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR         NOT NULL,
    otp_hash    VARCHAR         NOT NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ     NOT NULL,
    verified    BOOLEAN         NOT NULL DEFAULT FALSE,
    attempts    INTEGER         NOT NULL DEFAULT 0
);

-- Single-column indexes (present from initial creation of this table)
CREATE INDEX ix_email_otps_email      ON email_otps (email);
CREATE INDEX ix_email_otps_expires_at ON email_otps (expires_at);


-- =============================================================================
-- PHASE 3: Commit ffbccf5
-- "Production hardening upgrade, verification, and repo cleanup"
--
-- Changes:
--   1. query_logs: Added 2 new composite indexes
--   2. email_otps: Added index on created_at column + 2 composite indexes
--   3. Added 3 new tables: rate_limit_counters, otp_request_limits,
--      system_metrics
-- =============================================================================

-- -----------------------------------------------------------------------------
-- ALTERATION: query_logs — Added 2 new composite indexes
-- These supplement the existing idx_query_logs_user_timestamp and
-- idx_query_logs_risk_blocked from Phase 1.
-- -----------------------------------------------------------------------------
CREATE INDEX idx_query_logs_created ON query_logs (timestamp);
CREATE INDEX idx_query_logs_user    ON query_logs (user_id);

-- -----------------------------------------------------------------------------
-- ALTERATION: email_otps — Added index on created_at for cleanup performance
-- Previously created_at had no index on this column.
-- Also added __table_args__ composite indexes.
-- -----------------------------------------------------------------------------
CREATE INDEX ix_email_otps_created_at ON email_otps (created_at);

-- Composite indexes added via __table_args__
CREATE INDEX idx_emailotp_email   ON email_otps (email);
CREATE INDEX idx_emailotp_created ON email_otps (created_at);


-- -----------------------------------------------------------------------------
-- NEW TABLE: rate_limit_counters
-- Purpose: Database-backed sliding-window rate limit counters.
--          Enables O(1) UPSERT-based rate validation.
-- -----------------------------------------------------------------------------
CREATE TABLE rate_limit_counters (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier      VARCHAR         NOT NULL,
    endpoint        VARCHAR         NOT NULL,
    window_start    TIMESTAMPTZ     NOT NULL,
    request_count   INTEGER         NOT NULL DEFAULT 1
);

-- Single-column indexes
CREATE INDEX ix_rate_limit_counters_identifier   ON rate_limit_counters (identifier);
CREATE INDEX ix_rate_limit_counters_endpoint      ON rate_limit_counters (endpoint);
CREATE INDEX ix_rate_limit_counters_window_start  ON rate_limit_counters (window_start);

-- Composite indexes
CREATE UNIQUE INDEX idx_rate_limiter_identifier_window
    ON rate_limit_counters (identifier, endpoint, window_start);
CREATE INDEX idx_rate_created ON rate_limit_counters (window_start);
CREATE INDEX idx_rate_ip      ON rate_limit_counters (identifier);


-- -----------------------------------------------------------------------------
-- NEW TABLE: otp_request_limits
-- Purpose: Hardens OTP requests to prevent global resource exhaustion and
--          SMTP abuse. Tracks system-wide and IP-based counts.
-- -----------------------------------------------------------------------------
CREATE TABLE otp_request_limits (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR         NULL,
    ip_address          VARCHAR         NOT NULL,
    request_timestamp   TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Single-column indexes
CREATE INDEX ix_otp_request_limits_email               ON otp_request_limits (email);
CREATE INDEX ix_otp_request_limits_ip_address           ON otp_request_limits (ip_address);
CREATE INDEX ix_otp_request_limits_request_timestamp    ON otp_request_limits (request_timestamp);

-- Composite indexes
CREATE INDEX idx_otp_limit_email     ON otp_request_limits (email);
CREATE INDEX idx_otp_limit_ip        ON otp_request_limits (ip_address);
CREATE INDEX idx_otp_limit_timestamp ON otp_request_limits (request_timestamp);


-- -----------------------------------------------------------------------------
-- NEW TABLE: system_metrics
-- Purpose: Persisted telemetry metrics mapping cumulative usage statistics.
--          Key-value store that survives app restarts.
-- Note: Uses metric_name as primary key (not UUID).
-- -----------------------------------------------------------------------------
CREATE TABLE system_metrics (
    metric_name     VARCHAR         PRIMARY KEY,
    metric_value    FLOAT           NOT NULL DEFAULT 0.0,
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);


-- =============================================================================
-- PHASE 4: Commit 4aa59b5
-- "changes regarding scalability"
--
-- Added TSVECTOR import to support full-text search.
-- Added 3 new tables: documents, chunks, vector_maps
-- No changes to existing tables.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- NEW TABLE: documents
-- Purpose: Represents ingested PDF documents.
--          Uses SHA-256 hex digest as primary key.
-- -----------------------------------------------------------------------------
CREATE TABLE documents (
    id              VARCHAR         PRIMARY KEY,
    source_file     VARCHAR         NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_documents_source_file UNIQUE (source_file)
);

-- Single-column index
CREATE INDEX ix_documents_source_file ON documents (source_file);


-- -----------------------------------------------------------------------------
-- NEW TABLE: chunks
-- Purpose: Text chunks extracted from documents for RAG retrieval.
--          Supports full-text search via PostgreSQL TSVECTOR + GIN index.
-- -----------------------------------------------------------------------------
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

-- Single-column indexes
CREATE INDEX ix_chunks_doc_id      ON chunks (doc_id);
CREATE INDEX ix_chunks_page_number ON chunks (page_number);

-- Composite/special indexes
CREATE INDEX idx_chunks_tsv      ON chunks USING gin (tsv_content);
CREATE INDEX idx_chunks_doc_page ON chunks (doc_id, page_number);


-- -----------------------------------------------------------------------------
-- NEW TABLE: vector_maps
-- Purpose: Maps FAISS vector index offsets to text chunk IDs.
--          Bridges the vector store with the relational schema.
-- -----------------------------------------------------------------------------
CREATE TABLE vector_maps (
    vector_id   INTEGER         PRIMARY KEY,
    chunk_id    VARCHAR         NOT NULL,

    CONSTRAINT uq_vector_maps_chunk_id UNIQUE (chunk_id),
    CONSTRAINT fk_vector_maps_chunk_id FOREIGN KEY (chunk_id)
        REFERENCES chunks (chunk_id) ON DELETE CASCADE
);

-- Single-column index
CREATE INDEX ix_vector_maps_chunk_id ON vector_maps (chunk_id);


-- =============================================================================
-- RUNTIME MIGRATION (main.py lifespan handler)
--
-- Source: backend/main.py line 97
-- Purpose: Ensures the security_reason column exists on query_logs.
--          This column was already present in the initial model definition
--          (commit f6e0f09), so this migration serves as a safety net for
--          databases created before that column existed in the ORM.
-- =============================================================================

-- This ALTER TABLE runs at every application startup:
ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS security_reason TEXT;
