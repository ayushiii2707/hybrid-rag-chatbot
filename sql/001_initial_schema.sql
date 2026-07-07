-- =============================================================================
-- 001_initial_schema.sql
-- Earliest Known Database State
-- =============================================================================
--
-- Source: Commit f6e0f09 ("Initialize and update backend with Phase 3
--         Governance and Rate Limiting features")
--
-- This represents the initial database creation. At this point the schema
-- contained exactly 2 tables: users and query_logs.
--
-- Database: PostgreSQL
-- ORM: SQLAlchemy (declarative_base)
-- Table creation method: Base.metadata.create_all(bind=engine)
-- =============================================================================

-- Enable UUID generation (PostgreSQL)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- TABLE: users
-- Purpose: Enterprise system user identity and authentication
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

-- Single-column indexes on users (defined via Column(..., index=True))
CREATE INDEX ix_users_email      ON users (email);
CREATE INDEX ix_users_role       ON users (role);
CREATE INDEX ix_users_created_at ON users (created_at);


-- =============================================================================
-- TABLE: query_logs
-- Purpose: Persistent audit logs for RAG query pipeline
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

-- Single-column indexes on query_logs (defined via Column(..., index=True))
CREATE INDEX ix_query_logs_timestamp        ON query_logs (timestamp);
CREATE INDEX ix_query_logs_user_id          ON query_logs (user_id);
CREATE INDEX ix_query_logs_query_granularity ON query_logs (query_granularity);
CREATE INDEX ix_query_logs_blocked          ON query_logs (blocked);
CREATE INDEX ix_query_logs_risk_level       ON query_logs (risk_level);

-- Composite indexes on query_logs (defined via __table_args__)
CREATE INDEX idx_query_logs_user_timestamp  ON query_logs (user_id, timestamp);
CREATE INDEX idx_query_logs_risk_blocked    ON query_logs (risk_level, blocked);
