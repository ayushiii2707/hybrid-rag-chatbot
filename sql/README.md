# Database Schema Documentation

> **Authoritative SQL documentation for the Hybrid RAG Chatbot platform.**
> Generated from verified repository sources on 2026-07-07.

---

## Database Overview

This project uses **PostgreSQL** as its primary relational database, accessed through **SQLAlchemy ORM** with the `declarative_base` pattern. Tables are auto-created at application startup via `Base.metadata.create_all(bind=engine)` in the FastAPI lifespan handler. No formal migration framework (e.g., Alembic) is used; schema evolution is managed through ORM model changes and one runtime `ALTER TABLE` statement.

### Technology Stack

| Component         | Technology                          |
|-------------------|-------------------------------------|
| Database Engine   | PostgreSQL (default connection)     |
| ORM               | SQLAlchemy (declarative base)       |
| Web Framework     | FastAPI                             |
| Connection Pool   | SQLAlchemy pool (configurable)      |
| UUID Generation   | PostgreSQL `UUID` / Python `uuid4`  |
| Full-Text Search  | PostgreSQL `TSVECTOR` + GIN index   |
| JSON Storage      | PostgreSQL `JSONB`                  |

### Default Connection

```
postgresql://ayushiranjan@localhost/chatbot
```

Configurable via `DATABASE_URL` environment variable.

---

## Schema Evolution Summary

The database schema evolved across **4 major commits** (verified via `git log`):

| Phase | Commit       | Description                                                        | Tables Added                                          |
|-------|--------------|--------------------------------------------------------------------|-------------------------------------------------------|
| 1     | `f6e0f09`    | Initialize backend with Phase 3 Governance and Rate Limiting       | `users`, `query_logs`                                 |
| 2     | `35ca000`    | Implement persistent dual-mode OTP flow                            | `conversations`, `messages`, `email_otps`              |
| 3     | `ffbccf5`    | Production hardening upgrade, verification, and repo cleanup       | `rate_limit_counters`, `otp_request_limits`, `system_metrics` |
| 4     | `4aa59b5`    | Changes regarding scalability                                      | `documents`, `chunks`, `vector_maps`                  |

Additionally, a runtime schema migration in `main.py` ensures the `security_reason` column exists on the `query_logs` table.

---

## SQL Files — Execution Order

These files document the database schema. They should be read and (if needed) executed in numerical order:

| File                        | Purpose                                                            |
|-----------------------------|--------------------------------------------------------------------|
| `001_initial_schema.sql`    | Earliest known database state (Phase 1: `users` + `query_logs`)   |
| `002_schema_evolution.sql`  | Chronological schema changes across all phases                     |
| `003_indexes.sql`           | All indexes (single-column + composite) defined in the codebase    |
| `004_constraints.sql`       | All constraints (PK, FK, UNIQUE) defined in the codebase           |
| `005_seed_data.sql`         | Default seed data inserted at application startup                  |
| `006_final_schema.sql`      | Complete final database snapshot (all 10 tables)                   |
| `007_entity_relationship_diagram.md` | ER diagram, relationships, cascade rules, domain groups |

---

## Historical vs. Final Schema

- **Historical schema** (`001` + `002`): Reconstructs the database as it evolved commit-by-commit, showing which tables and columns were added at each stage.
- **Final schema** (`006`): Represents the current state of the database — what you would get by running `Base.metadata.create_all()` against the latest codebase.

No tables or columns have been **removed** during the project's history. The schema has only grown additively.

---

## Database Recreation

To recreate the database from scratch using these SQL files:

```bash
# 1. Create the PostgreSQL database
createdb chatbot

# 2. Run the final schema (creates all tables, indexes, and constraints)
psql -d chatbot -f sql/006_final_schema.sql

# 3. (Optional) Insert seed data
psql -d chatbot -f sql/005_seed_data.sql
```

Alternatively, the application auto-creates all tables on startup:

```bash
cd backend
uvicorn main:app --reload
```

---

## Source Verification

All SQL in this documentation was generated exclusively from:

1. **SQLAlchemy ORM models** in `backend/auth/auth_models.py`
2. **Database configuration** in `backend/database/db.py`
3. **Runtime migration** in `backend/main.py` (line 97)
4. **Seed data logic** in `backend/main.py` (lines 74–89)
5. **Git history** across commits `f6e0f09` → `35ca000` → `ffbccf5` → `4aa59b5`

No fictional or assumed database objects were created.
