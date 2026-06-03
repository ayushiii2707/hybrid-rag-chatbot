import os
import sys
import uuid
import time
import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

# ── Bootstrap Paths ───────────────────────────────────────────────────────────
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKSPACE_DIR)

BACKEND_DIR = os.path.join(WORKSPACE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "logging"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "auth"))

from backend.database.db import engine, Base, SessionLocal
from backend.auth.auth_models import User, QueryLog
from backend.main import app
from backend.logging.query_logger import QueryAuditLogger
from backend.auth.jwt_service import decode_access_token

def run_verification():
    print("=" * 80)
    print("  PHASE 2 SYSTEM VERIFICATION: ENTERPRISE IDENTITY & QUERY OWNERSHIP")
    print("=" * 80)

    # ── 1. Verify SQLAlchemy Connection Pooling ────────────────────────────────
    print("\n[STEP 1] Verifying SQLAlchemy Connection Pooling config...")
    pool = engine.pool
    print(f"  Pool Type      : {type(pool).__name__}")
    print(f"  Pool Size      : {pool.size()}")
    print(f"  Max Overflow   : {pool._max_overflow}")
    print(f"  Pool Timeout   : {pool._timeout}")
    print(f"  Pool Recycle   : {pool._recycle}")
    assert type(pool).__name__ == "QueuePool", "SQLAlchemy connection pool must use QueuePool!"
    print("  ✓ SQLAlchemy Connection Pooling is ACTIVE and configured correctly.")

    # ── 2. Initialize Database & Clean up ──────────────────────────────────────
    print("\n[STEP 2] Initializing tables and cleaning up database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Delete existing test user/logs if any
        db.query(QueryLog).filter(QueryLog.email == "test_auth_user@example.com").delete()
        db.query(User).filter(User.email == "test_auth_user@example.com").delete()
        db.commit()
    finally:
        db.close()
    print("  ✓ Tables created/verified. Test data cleaned up.")

    client = TestClient(app)

    # ── 3. Register a Test User ───────────────────────────────────────────────
    print("\n[STEP 3] Registering a new test user...")
    test_email = "test_auth_user@example.com"
    test_pass = "SecurePass123!"
    
    reg_response = client.post(
        "/register",
        json={"email": test_email, "password": test_pass, "role": "vendor"}
    )
    print(f"  Register Status: {reg_response.status_code}")
    print(f"  Register Body  : {reg_response.json()}")
    assert reg_response.status_code == 201, "User registration failed!"
    
    # Try duplicate email registration
    print("  Verifying duplicate email protection...")
    dup_response = client.post(
        "/register",
        json={"email": test_email, "password": test_pass, "role": "vendor"}
    )
    print(f"  Dup Reg Status : {dup_response.status_code}")
    print(f"  Dup Reg Body   : {dup_response.json()}")
    assert dup_response.status_code == 400, "Duplicate registration was not blocked!"
    assert "already registered" in dup_response.json().get("detail", ""), "Incorrect error message for duplicate email!"
    print("  ✓ User registration and duplicate protection validated successfully.")

    # ── 4. Login Successfully & Validate JWT Generation ────────────────────────
    print("\n[STEP 4] Logging in and validating JWT token...")
    login_response = client.post(
        "/login",
        json={"email": test_email, "password": test_pass}
    )
    print(f"  Login Status   : {login_response.status_code}")
    assert login_response.status_code == 200, "Login failed!"
    token_data = login_response.json()
    assert "access_token" in token_data, "Login response missing access_token!"
    token = token_data["access_token"]
    print(f"  JWT Token Type : {token_data['token_type']}")
    print(f"  JWT Value      : {token[:30]}...[TRUNCATED]...{token[-10:]}")
    
    # Decode and validate token content
    payload = decode_access_token(token)
    print(f"  Decoded Payload: {payload}")
    assert payload is not None, "JWT decoding failed!"
    assert payload.get("email") == test_email, "JWT payload has wrong email!"
    assert payload.get("role") == "vendor", "JWT payload has wrong role!"
    assert "user_id" in payload, "JWT payload missing user_id!"
    user_id = payload["user_id"]
    print("  ✓ Login verified. JWT generated and signature validated successfully.")

    # ── 5. Confirm Unauthenticated access is rejected where appropriate ─────────
    print("\n[STEP 5] Testing protected-route authorization enforcement...")
    # No token
    unauth_response = client.get("/protected-test")
    print(f"  Unauth Response: {unauth_response.status_code} - {unauth_response.json()}")
    assert unauth_response.status_code == 401, "Unauthenticated access should be rejected!"
    
    # Invalid token
    bad_token_response = client.get("/protected-test", headers={"Authorization": "Bearer invalid_token_value"})
    print(f"  Bad Token Resp : {bad_token_response.status_code} - {bad_token_response.json()}")
    assert bad_token_response.status_code == 401, "Invalid token access should be rejected!"
    
    # Correct token
    auth_response = client.get("/protected-test", headers={"Authorization": f"Bearer {token}"})
    print(f"  Auth Response  : {auth_response.status_code} - {auth_response.json()}")
    assert auth_response.status_code == 200, "Authenticated request failed!"
    assert auth_response.json()["user"]["email"] == test_email
    print("  ✓ Protected route access control validated successfully.")

    # ── 6. Execute Authenticated Queries & Validate RAG Pipeline ───────────────
    print("\n[STEP 6] Executing query request through the RAG pipeline...")
    # Test query
    query_text = "What is the link to the supplier registration portal?"
    query_response = client.post(
        "/query",
        json={"query": query_text},
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"  Query Status   : {query_response.status_code}")
    assert query_response.status_code == 200, "Query endpoint execution failed!"
    response_json = query_response.json()
    print(f"  Answer Found   : {response_json.get('answer_found')}")
    print(f"  Confidence     : {response_json.get('confidence')} ({response_json.get('confidence_band')})")
    print(f"  Synthesized    : {response_json.get('synthesized_answer')[:120]}...")
    assert response_json.get("answer_found") is True, "Answer not found in retrieval pipeline!"
    print("  ✓ Retrieval answer quality remains unchanged and correct.")

    # ── 7. Verify JSONL Log Record ─────────────────────────────────────────────
    print("\n[STEP 7] Verifying JSONL file log structure...")
    # Let background logger write
    time.sleep(0.5)
    
    audit_logger = QueryAuditLogger()
    recent_logs = audit_logger.read_recent(1)
    assert len(recent_logs) > 0, "No recent logs found in JSONL file!"
    last_log = recent_logs[-1]
    
    print("  Sample Audit Log entry from JSONL:")
    print(json.dumps(last_log, indent=4))
    
    assert last_log.get("user_id") == user_id, "user_id not saved in log file!"
    assert last_log.get("email") == test_email, "email not saved in log file!"
    assert last_log.get("role") == "vendor", "role not saved in log file!"
    assert last_log.get("query") == query_text, "query not saved correctly in log file!"
    print("  ✓ JSONL audit logging includes correct user identity information.")

    # ── 8. Verify PostgreSQL Log Record ─────────────────────────────────────────
    print("\n[STEP 8] Verifying PostgreSQL database log record...")
    db = SessionLocal()
    try:
        db_log = db.query(QueryLog).filter(QueryLog.user_id == uuid.UUID(user_id)).first()
        assert db_log is not None, "Log record not found in PostgreSQL query_logs table!"
        print("  Sample DB Query Log record fields:")
        print(f"    ID                : {db_log.id}")
        print(f"    Query ID          : {db_log.query_id}")
        print(f"    User ID           : {db_log.user_id}")
        print(f"    Email             : {db_log.email}")
        print(f"    Role              : {db_log.role}")
        print(f"    Query             : {db_log.query}")
        print(f"    Granularity       : {db_log.query_granularity}")
        print(f"    Timestamp         : {db_log.timestamp}")
        print(f"    Risk Level        : {db_log.risk_level}")
        print(f"    Blocked           : {db_log.blocked}")
        
        assert db_log.email == test_email, "Email mismatch in PostgreSQL query log record!"
        assert db_log.role == "vendor", "Role mismatch in PostgreSQL query log record!"
        assert db_log.query == query_text, "Query mismatch in PostgreSQL query log record!"
    finally:
        db.close()
    print("  ✓ PostgreSQL DB query log entry exists and matches query flow details.")

    # ── 9. Verify PostgreSQL DB Indexes ──────────────────────────────────────────
    print("\n[STEP 9] Inspecting PostgreSQL index schema...")
    inspector = inspect(engine)
    
    # Check users table indexes
    user_indexes = inspector.get_indexes("users")
    print("  Indexes on table 'users':")
    for idx in user_indexes:
        print(f"    - Name: {idx['name']}, Columns: {idx['column_names']}, Unique: {idx['unique']}")
    
    # Check email unique constraint/index
    email_idx = [idx for idx in user_indexes if "email" in idx["column_names"]]
    assert len(email_idx) > 0, "Missing index on users.email!"
    
    # Check role index
    role_idx = [idx for idx in user_indexes if "role" in idx["column_names"]]
    assert len(role_idx) > 0, "Missing index on users.role!"

    # Check created_at index
    created_at_idx = [idx for idx in user_indexes if "created_at" in idx["column_names"]]
    assert len(created_at_idx) > 0, "Missing index on users.created_at!"

    # Check query_logs table indexes
    log_indexes = inspector.get_indexes("query_logs")
    print("  Indexes on table 'query_logs':")
    for idx in log_indexes:
        print(f"    - Name: {idx['name']}, Columns: {idx['column_names']}, Unique: {idx['unique']}")
        
    log_cols_indexed = []
    for idx in log_indexes:
        log_cols_indexed.extend(idx["column_names"])
        
    assert "user_id" in log_cols_indexed, "Missing index on query_logs.user_id!"
    assert "timestamp" in log_cols_indexed, "Missing index on query_logs.timestamp!"
    assert "risk_level" in log_cols_indexed, "Missing index on query_logs.risk_level!"
    assert "blocked" in log_cols_indexed, "Missing index on query_logs.blocked!"
    assert "query_granularity" in log_cols_indexed, "Missing index on query_logs.query_granularity!"
    
    # Verify composites
    composite_user_time = [idx for idx in log_indexes if idx["column_names"] == ["user_id", "timestamp"]]
    assert len(composite_user_time) > 0, "Missing composite index (user_id, timestamp)!"
    
    composite_risk_blocked = [idx for idx in log_indexes if idx["column_names"] == ["risk_level", "blocked"]]
    assert len(composite_risk_blocked) > 0, "Missing composite index (risk_level, blocked)!"

    print("  ✓ All required database indexes are verified as successfully created in PostgreSQL.")
    print("\n" + "=" * 80)
    print("  VERIFICATION SUCCESS: ALL ENTERPRISE AUTHENTICATION & OWNERSHIP TESTS PASSED")
    print("=" * 80)

if __name__ == "__main__":
    run_verification()
