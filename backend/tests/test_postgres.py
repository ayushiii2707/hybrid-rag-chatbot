import unittest
import os
import sys
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database.db import get_db, Base
from backend.auth.auth_models import User, RateLimitCounter, OTPRequestLimit, QueryLog, SystemMetric
from backend.auth.jwt_service import create_access_token

# Real PostgreSQL test setup using the project's DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ayushiranjan@localhost/chatbot")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Override SessionLocal inside the backend components for integration test isolation
import backend.auth.middleware
import backend.database.db
import backend.logging.query_logger
from backend.auth.rate_limit import check_rate_limit
backend.auth.middleware.check_rate_limit = check_rate_limit # Force use of real pg upsert method
backend.auth.middleware.SessionLocal = TestingSessionLocal
backend.database.db.SessionLocal = TestingSessionLocal
backend.database.db.engine = engine
backend.logging.query_logger.SessionLocal = TestingSessionLocal

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

class TestPostgresProduction(unittest.TestCase):
    def setUp(self):
        # Bind the schemas directly to local PostgreSQL
        Base.metadata.create_all(bind=engine)
        db = TestingSessionLocal()
        try:
            db.execute(text("TRUNCATE TABLE system_metrics, rate_limit_counters, otp_request_limits, query_logs CASCADE;"))
            db.execute(text("INSERT INTO system_metrics (metric_name, metric_value) VALUES ('queries_total', 0.0) ON CONFLICT(metric_name) DO NOTHING;"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def test_postgres_security_headers(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_postgres_health_endpoint(self):
        response = client.get("/health")
        data = response.json()
        self.assertEqual(data["database"], "connected")

    def test_postgres_rate_limiting(self):
        # Clear rate limit tables to ensure a clean window check
        # "Cleaned rate limit tables dynamically inside postgres test runner to verify 429 redirects"
        db = TestingSessionLocal()
        try:
            db.execute(text("TRUNCATE TABLE rate_limit_counters;"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        payload = {"user_id": "99999999-9999-9999-9999-999999999999", "email": "test_pg_rate@ril.com", "role": "vendor"}
        token = create_access_token(data=payload)
        headers = {"Authorization": f"Bearer {token}"}

        # Override rate limit configurations dynamically
        import backend.auth.rate_limit
        old_max = backend.auth.rate_limit.MAX_REQUESTS
        backend.auth.rate_limit.MAX_REQUESTS = 3

        try:
            responses = []
            # Make sure we hit the endpoint consecutively
            for _ in range(6):
                res = client.get("/protected-test", headers=headers)
                responses.append(res)
            
            status_codes = [r.status_code for r in responses]
            self.assertIn(429, status_codes)
        finally:
            backend.auth.rate_limit.MAX_REQUESTS = old_max

    def test_cleanup_functionality(self):
        # Verify background cleanup execution directly on PostgreSQL
        from backend.services.cleanup import run_database_cleanup
        db = TestingSessionLocal()
        try:
            # Seed expired records manually
            past_time = datetime.now(timezone.utc) - timedelta(days=2)
            
            # Seed old rate limit
            rate_entry = RateLimitCounter(
                identifier="old_ip",
                endpoint="/test",
                window_start=past_time,
                request_count=10
            )
            db.add(rate_entry)
            db.commit()

            # Run cleanup operation
            run_database_cleanup(db)

            # Assert record was deleted according to retention policy
            remaining = db.query(RateLimitCounter).filter(RateLimitCounter.identifier == "old_ip").count()
            self.assertEqual(remaining, 0)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
