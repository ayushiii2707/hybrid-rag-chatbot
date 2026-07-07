-- =============================================================================
-- 004_constraints.sql
-- Complete Constraint Documentation
-- =============================================================================
--
-- Every constraint defined in the codebase is documented here, organized by
-- table. Constraints are derived from SQLAlchemy model definitions in
-- backend/auth/auth_models.py.
--
-- Constraint types present:
--   - PRIMARY KEY  (every table has one)
--   - FOREIGN KEY  (with ON DELETE actions)
--   - UNIQUE       (on specific columns)
--
-- Constraint types NOT present in this project:
--   - CHECK constraints  (none defined in models)
--   - EXCLUDE constraints (none defined)
--
-- Note: No constraints were ever removed during the project's history.
-- =============================================================================


-- =============================================================================
-- TABLE: users
-- =============================================================================

-- Primary Key
ALTER TABLE users
    ADD CONSTRAINT pk_users PRIMARY KEY (id);

-- Unique Constraint
ALTER TABLE users
    ADD CONSTRAINT uq_users_email UNIQUE (email);


-- =============================================================================
-- TABLE: query_logs
-- =============================================================================

-- Primary Key
ALTER TABLE query_logs
    ADD CONSTRAINT pk_query_logs PRIMARY KEY (id);

-- Unique Constraint
ALTER TABLE query_logs
    ADD CONSTRAINT uq_query_logs_query_id UNIQUE (query_id);

-- Foreign Key: user_id → users.id (ON DELETE SET NULL)
-- Rationale: When a user is deleted, their query logs are preserved with
-- user_id set to NULL for audit trail purposes.
ALTER TABLE query_logs
    ADD CONSTRAINT fk_query_logs_user_id
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL;


-- =============================================================================
-- TABLE: conversations
-- =============================================================================

-- Primary Key
ALTER TABLE conversations
    ADD CONSTRAINT pk_conversations PRIMARY KEY (id);

-- Foreign Key: user_id → users.id (ON DELETE CASCADE)
-- Rationale: When a user is deleted, all their conversations are
-- automatically removed.
ALTER TABLE conversations
    ADD CONSTRAINT fk_conversations_user_id
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE;


-- =============================================================================
-- TABLE: messages
-- =============================================================================

-- Primary Key
ALTER TABLE messages
    ADD CONSTRAINT pk_messages PRIMARY KEY (id);

-- Foreign Key: conversation_id → conversations.id (ON DELETE CASCADE)
-- Rationale: When a conversation is deleted, all its messages are
-- automatically removed.
ALTER TABLE messages
    ADD CONSTRAINT fk_messages_conversation_id
    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE;


-- =============================================================================
-- TABLE: email_otps
-- =============================================================================

-- Primary Key
ALTER TABLE email_otps
    ADD CONSTRAINT pk_email_otps PRIMARY KEY (id);

-- No foreign keys (email is stored as a plain string, not linked to users.id)
-- No unique constraints (multiple OTPs can exist for the same email)


-- =============================================================================
-- TABLE: rate_limit_counters
-- =============================================================================

-- Primary Key
ALTER TABLE rate_limit_counters
    ADD CONSTRAINT pk_rate_limit_counters PRIMARY KEY (id);

-- Unique Composite Constraint (via unique index in __table_args__)
-- Enforced through: Index("idx_rate_limiter_identifier_window", ..., unique=True)
-- Purpose: Ensures one counter per (identifier, endpoint, window_start) tuple
--          to support UPSERT-based rate limiting.
ALTER TABLE rate_limit_counters
    ADD CONSTRAINT uq_rate_limit_counters_identifier_endpoint_window
    UNIQUE (identifier, endpoint, window_start);


-- =============================================================================
-- TABLE: otp_request_limits
-- =============================================================================

-- Primary Key
ALTER TABLE otp_request_limits
    ADD CONSTRAINT pk_otp_request_limits PRIMARY KEY (id);

-- No foreign keys
-- No unique constraints (multiple records per email/IP are expected)


-- =============================================================================
-- TABLE: system_metrics
-- =============================================================================

-- Primary Key (VARCHAR — uses metric_name as natural key, not UUID)
ALTER TABLE system_metrics
    ADD CONSTRAINT pk_system_metrics PRIMARY KEY (metric_name);

-- No foreign keys
-- No additional unique constraints


-- =============================================================================
-- TABLE: documents
-- =============================================================================

-- Primary Key (VARCHAR — uses SHA-256 hex digest as document ID)
ALTER TABLE documents
    ADD CONSTRAINT pk_documents PRIMARY KEY (id);

-- Unique Constraint
ALTER TABLE documents
    ADD CONSTRAINT uq_documents_source_file UNIQUE (source_file);


-- =============================================================================
-- TABLE: chunks
-- =============================================================================

-- Primary Key (VARCHAR — uses chunk_id string)
ALTER TABLE chunks
    ADD CONSTRAINT pk_chunks PRIMARY KEY (chunk_id);

-- Foreign Key: doc_id → documents.id (ON DELETE CASCADE)
-- Rationale: When a document is deleted, all its chunks are automatically
-- removed.
ALTER TABLE chunks
    ADD CONSTRAINT fk_chunks_doc_id
    FOREIGN KEY (doc_id) REFERENCES documents (id) ON DELETE CASCADE;


-- =============================================================================
-- TABLE: vector_maps
-- =============================================================================

-- Primary Key (INTEGER — FAISS vector index offset)
ALTER TABLE vector_maps
    ADD CONSTRAINT pk_vector_maps PRIMARY KEY (vector_id);

-- Unique Constraint
ALTER TABLE vector_maps
    ADD CONSTRAINT uq_vector_maps_chunk_id UNIQUE (chunk_id);

-- Foreign Key: chunk_id → chunks.chunk_id (ON DELETE CASCADE)
-- Rationale: When a chunk is deleted, its vector mapping is automatically
-- removed.
ALTER TABLE vector_maps
    ADD CONSTRAINT fk_vector_maps_chunk_id
    FOREIGN KEY (chunk_id) REFERENCES chunks (chunk_id) ON DELETE CASCADE;


-- =============================================================================
-- CONSTRAINT SUMMARY
-- =============================================================================
--
-- Total constraints: 22
--
-- By type:
--   PRIMARY KEY:   10  (one per table)
--   FOREIGN KEY:    5  (query_logs→users, conversations→users,
--                       messages→conversations, chunks→documents,
--                       vector_maps→chunks)
--   UNIQUE:         5  (users.email, query_logs.query_id,
--                       documents.source_file, vector_maps.chunk_id,
--                       rate_limit_counters composite)
--   CHECK:          0  (none defined in codebase)
--
-- Foreign Key ON DELETE actions:
--   SET NULL:       1  (query_logs.user_id)
--   CASCADE:        4  (conversations.user_id, messages.conversation_id,
--                       chunks.doc_id, vector_maps.chunk_id)
--
-- =============================================================================
