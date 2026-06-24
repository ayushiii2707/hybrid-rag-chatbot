import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

# Sliding-window rate limit window duration in seconds
WINDOW_SECONDS = 10
MAX_REQUESTS = 15

def check_rate_limit(db: Session, identifier: str, endpoint: str) -> tuple[bool, int]:
    """
    Checks rate limit by performing a PostgreSQL UPSERT.
    Returns:
        tuple (is_blocked, retry_after_seconds)
    """
    now = datetime.now(timezone.utc)
    epoch = int(now.timestamp())
    window_epoch = epoch - (epoch % WINDOW_SECONDS)
    window_start = datetime.fromtimestamp(window_epoch, tz=timezone.utc)

    # Support SQLite for local tests by checking bind dialect name. Every modification includes this explanatory comment:
    # "Added SQLite dialect compatibility fallback to support unit-tests without PostgreSQL gen_random_uuid dependencies"
    is_sqlite = db.bind.dialect.name == "sqlite"
    if is_sqlite:
        import uuid
        sql = text("""
            INSERT INTO rate_limit_counters (id, identifier, endpoint, window_start, request_count)
            VALUES (:id, :identifier, :endpoint, :window_start, 1)
            ON CONFLICT (identifier, endpoint, window_start)
            DO UPDATE SET request_count = rate_limit_counters.request_count + 1
            RETURNING request_count;
        """)
        params = {
            "id": str(uuid.uuid4()),
            "identifier": identifier,
            "endpoint": endpoint,
            "window_start": window_start
        }
    else:
        sql = text("""
            INSERT INTO rate_limit_counters (id, identifier, endpoint, window_start, request_count)
            VALUES (gen_random_uuid(), :identifier, :endpoint, :window_start, 1)
            ON CONFLICT (identifier, endpoint, window_start)
            DO UPDATE SET request_count = rate_limit_counters.request_count + 1
            RETURNING request_count;
        """)
        params = {
            "identifier": identifier,
            "endpoint": endpoint,
            "window_start": window_start
        }

    try:
        result = db.execute(sql, params)
        db.commit()
        row = result.fetchone()
        count = row[0] if row else 1

        from backend.auth.rate_limit import MAX_REQUESTS as CURRENT_MAX
        if count > CURRENT_MAX:
            retry_after = WINDOW_SECONDS - (epoch % WINDOW_SECONDS)
            return True, retry_after
    except Exception as e:
        db.rollback()
        logger.error(f"Error executing rate limit upsert: {e}")
        return False, 0

    return False, 0
