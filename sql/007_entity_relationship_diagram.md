# Entity-Relationship Diagram

> Database relationships for the Hybrid RAG Chatbot platform.

---

## Visual ER Diagram

```mermaid
erDiagram
    users ||--o{ query_logs : "logs queries"
    users ||--o{ conversations : "owns"
    conversations ||--o{ messages : "contains"
    documents ||--o{ chunks : "split into"
    chunks ||--o| vector_maps : "mapped to"

    users {
        UUID id PK
        VARCHAR email UK
        VARCHAR hashed_password
        VARCHAR role
        VARCHAR status
        TIMESTAMPTZ created_at
        TIMESTAMPTZ last_login
    }

    query_logs {
        UUID id PK
        VARCHAR query_id UK
        TIMESTAMPTZ timestamp
        UUID user_id FK
        VARCHAR email
        VARCHAR role
        TEXT query
        TEXT corrected_query
        VARCHAR query_granularity
        BOOLEAN answer_found
        BOOLEAN partial_match_found
        FLOAT confidence
        VARCHAR confidence_band
        VARCHAR top_source_file
        INTEGER top_page_number
        VARCHAR top_chunk_id
        JSONB retrieved_sources
        INTEGER response_length
        INTEGER processing_time_ms
        BOOLEAN blocked
        VARCHAR risk_level
        TEXT security_reason
        VARCHAR system_status
    }

    conversations {
        UUID id PK
        UUID user_id FK
        VARCHAR title
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
        BOOLEAN is_deleted
    }

    messages {
        UUID id PK
        UUID conversation_id FK
        VARCHAR role
        TEXT content
        TIMESTAMPTZ created_at
    }

    email_otps {
        UUID id PK
        VARCHAR email
        VARCHAR otp_hash
        TIMESTAMPTZ created_at
        TIMESTAMPTZ expires_at
        BOOLEAN verified
        INTEGER attempts
    }

    rate_limit_counters {
        UUID id PK
        VARCHAR identifier
        VARCHAR endpoint
        TIMESTAMPTZ window_start
        INTEGER request_count
    }

    otp_request_limits {
        UUID id PK
        VARCHAR email
        VARCHAR ip_address
        TIMESTAMPTZ request_timestamp
    }

    system_metrics {
        VARCHAR metric_name PK
        FLOAT metric_value
        TIMESTAMPTZ updated_at
    }

    documents {
        VARCHAR id PK
        VARCHAR source_file UK
        TIMESTAMPTZ created_at
    }

    chunks {
        VARCHAR chunk_id PK
        VARCHAR doc_id FK
        INTEGER page_number
        INTEGER chunk_index
        TEXT text
        VARCHAR section_title
        VARCHAR subsection_title
        VARCHAR procedure_id
        JSONB alternate_phrasings
        TSVECTOR tsv_content
    }

    vector_maps {
        INTEGER vector_id PK
        VARCHAR chunk_id FK_UK
    }
```

---

## Relationship Table

| Parent Table      | Child Table        | Type | FK Column          | ON DELETE   | Purpose                                        |
|-------------------|--------------------|------|--------------------|-------------|------------------------------------------------|
| `users`           | `query_logs`       | 1:N  | `user_id`          | `SET NULL`  | Preserves audit logs when user is deleted       |
| `users`           | `conversations`    | 1:N  | `user_id`          | `CASCADE`   | Deletes all conversations when user is deleted  |
| `conversations`   | `messages`         | 1:N  | `conversation_id`  | `CASCADE`   | Deletes all messages when conversation removed  |
| `documents`       | `chunks`           | 1:N  | `doc_id`           | `CASCADE`   | Deletes chunks when source document is removed  |
| `chunks`          | `vector_maps`      | 1:1  | `chunk_id`         | `CASCADE`   | Removes vector mapping when chunk is deleted    |

---

## Domain Groups

The 10 tables belong to 4 logical domains:

### 🔐 Authentication & Identity
```
users
  └── The central identity table. All user-facing tables reference this.
```

### 💬 Chat Persistence
```
users
  │
  ├── 1:N ── conversations
  │             │
  │             └── 1:N ── messages
  │
  └── 1:N ── query_logs  (audit trail, SET NULL on delete)
```

### 📄 RAG Document Pipeline
```
documents
  │
  └── 1:N ── chunks
                │
                └── 1:1 ── vector_maps  (FAISS bridge)
```

### ⚙️ Security & Infrastructure (standalone tables, no FK relationships)
```
email_otps           — OTP verification codes
rate_limit_counters  — Sliding-window rate limiting
otp_request_limits   — SMTP abuse prevention
system_metrics       — Telemetry counters (key-value)
```

---

## Cascade Deletion Flow

When a **user** is deleted:
```
DELETE users WHERE id = ?
  ├── CASCADE → conversations
  │               └── CASCADE → messages
  └── SET NULL → query_logs.user_id  (audit preserved)
```

When a **document** is deleted:
```
DELETE documents WHERE id = ?
  └── CASCADE → chunks
                  └── CASCADE → vector_maps
```

---

## Notes

- **No circular references** exist in the schema
- **No join tables** exist (no many-to-many relationships)
- **Standalone tables** (`email_otps`, `rate_limit_counters`, `otp_request_limits`, `system_metrics`) have no foreign key relationships — they are designed for high-throughput insert/delete patterns where FK overhead would be counterproductive
- The `query_logs.email` and `query_logs.role` columns denormalize user data for audit purposes (avoiding JOINs in log queries)
