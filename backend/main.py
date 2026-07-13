import os
import sys
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

# ── Bootstrap Paths ───────────────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, WORKSPACE_DIR)
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "logging"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "auth"))

from dotenv import load_dotenv
dotenv_path = os.path.join(BACKEND_DIR, ".env")
load_dotenv(dotenv_path, override=True)
from sqlalchemy import text

from backend.database.db import engine, Base, get_db, SessionLocal
from backend.auth.auth_models import User, EmailOTP
from backend.auth.auth_service import register_user, authenticate_user
from backend.auth.jwt_service import create_access_token
from backend.auth.middleware import JWTAuthMiddleware, get_optional_user, get_current_user
from backend.chat_router import router as chat_router
from backend.auth.otp_router import router as otp_router
from query_orchestrator import QueryOrchestrator

# Start background scheduler threads for retention pruning and JSONL sync. Every modification includes this explanatory comment:
# "Initiated non-blocking background threads in app lifespan to periodically prune expired OTPs/rate limits and sync audit logs"
import threading
def background_scheduler_worker():
    import time
    from backend.services.cleanup import run_database_cleanup
    from backend.logging.query_logger import QueryAuditLogger
    audit_logger = QueryAuditLogger()

    while True:
        # Run cleanup job every hour
        try:
            with SessionLocal() as db_session:
                run_database_cleanup(db_session)
        except Exception as err:
            sys.stderr.write(f"Background Cleanup Error: {err}\n")

        # Run JSONL failover sync to database
        try:
            audit_logger.sync_failed_logs()
        except Exception as err:
            sys.stderr.write(f"Background Log Sync Error: {err}\n")

        # Repeat every 3600 seconds
        time.sleep(3600)


# ── Lifespan for Startup and Shutdown Events ──────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    Base.metadata.create_all(bind=engine)

    # Seed default user accounts for manual validation/testing
    try:
        from backend.auth.auth_service import register_user
        from backend.auth.auth_models import User
        with SessionLocal() as db_session:
            default_users = [
                ("ayushir2707@gmail.com", "vendor"),
                ("swadha945@gmail.com", "vendor"),
                ("ayushihihi7@gmail.com", "vendor"),
                ("admin@ril.com", "admin")
            ]
            for email, role in default_users:
                exists = db_session.query(User).filter(User.email == email.lower()).first()
                if not exists:
                    register_user(
                        db=db_session,
                        email=email.lower(),
                        password_raw="Password123!",
                        role=role
                    )
                    sys.stdout.write(f"Startup Seed: Created default user {email} ({role}) with password 'Password123!'\n")
    except Exception as seed_err:
        sys.stderr.write(f"Warning: Failed to seed default users: {seed_err}\n")
    
    # Run schema migration dynamically to ensure security_reason column exists
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS security_reason TEXT;"))
            conn.commit()
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to run security_reason schema migration: {e}\n")

    # Start the background task executor
    scheduler_thread = threading.Thread(target=background_scheduler_worker, daemon=True)
    scheduler_thread.start()

    # Delete expired OTP records on startup to prevent table growth
    try:
        from datetime import datetime, timezone
        with SessionLocal() as db_session:
            expired_deleted = db_session.query(EmailOTP).filter(EmailOTP.expires_at < datetime.now(timezone.utc)).delete(synchronize_session=False)
            db_session.commit()
            if expired_deleted > 0:
                sys.stdout.write(f"Startup Cleanup: Deleted {expired_deleted} expired OTP records.\n")
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to clean up expired OTPs on startup: {e}\n")

    # Validate SMTP configuration on startup
    from backend.services.email_service import ENVIRONMENT, DEV_OTP_ENABLED
    if ENVIRONMENT == "development" and DEV_OTP_ENABLED:
        sys.stdout.write("==================================\n")
        sys.stdout.write("OTP MODE: DEVELOPMENT\n")
        sys.stdout.write("SMTP REQUIRED: NO\n")
        sys.stdout.write("DEV OTP BYPASS: ENABLED\n")
        sys.stdout.write("==================================\n")
    else:
        sys.stdout.write("==================================\n")
        sys.stdout.write("OTP MODE: PRODUCTION\n")
        sys.stdout.write("SMTP REQUIRED: YES\n")
        sys.stdout.write("DEV OTP BYPASS: DISABLED\n")
        sys.stdout.write("==================================\n")
    sys.stdout.flush()

    # Track startup timestamp for health metrics
    app.state.startup_time = time.time()

    yield

# Initialize FastAPI with metadata
app = FastAPI(
    title="Platform RAG Chatbot API",
    description="Enterprise Multi-User RAG Platform Foundation",
    version="1.0.0",
    lifespan=lifespan
)

from backend.auth.middleware import SecurityHeadersMiddleware

# Register Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Register CORS Middleware — must be added before JWT middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5000",
        "http://localhost:5001",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5000",
        "http://127.0.0.1:5001",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register JWT Middleware
app.add_middleware(JWTAuthMiddleware)

# Mount chat history router
app.include_router(chat_router)

# Mount OTP verification router
app.include_router(otp_router)

# Mount Admin Router
from backend.auth.admin_router import router as admin_router
app.include_router(admin_router)

# Initialize Query Orchestrator
orchestrator = QueryOrchestrator()

# Reusable bearer scheme to register Authorize button in Swagger UI
reusable_oauth2 = HTTPBearer(auto_error=False)



# ── Request / Response Models ──────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = "vendor"

class RegisterResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class QueryRequest(BaseModel):
    query: str
    answer_satisfied: Optional[bool] = None
    last_chunk_id: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(request_data: RegisterRequest, db: Session = Depends(get_db)):
    """
    Registers a new enterprise user.
    Enforces that email OTP verification is complete and valid.
    """
    from datetime import datetime, timezone
    # Normalize email to lowercase and strip whitespace
    email = request_data.email.strip().lower()
    now = datetime.now(timezone.utc)

    # 1. Verify OTP record exists and is marked verified
    otp_record = db.query(EmailOTP).filter(
        EmailOTP.email == email,
        EmailOTP.verified == True
    ).order_by(EmailOTP.created_at.desc()).first()

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is not verified. Please verify your email first."
        )

    # 2. Check if the verification has expired
    if otp_record.expires_at < now:
        db.delete(otp_record)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please verify your email again."
        )

    # 3. Create user
    db_user = register_user(
        db=db,
        email=email,
        password_raw=request_data.password,
        role=request_data.role
    )

    # 4. Delete the consumed OTP record
    db.delete(otp_record)
    db.commit()

    return RegisterResponse(
        id=str(db_user.id),
        email=db_user.email,
        role=db_user.role,
        status=db_user.status
    )


@app.post("/login", response_model=TokenResponse)
def login(request_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates a user and returns a stateless JWT.
    """
    # Normalize email to lowercase and strip whitespace
    email = request_data.email.strip().lower()

    db_user = authenticate_user(
        db=db,
        email=email,
        password_raw=request_data.password
    )
    # Generate token payload
    payload = {
        "user_id": str(db_user.id),
        "email": db_user.email,
        "role": db_user.role
    }
    token = create_access_token(data=payload)
    return TokenResponse(access_token=token, token_type="bearer")


class QueryResponse(BaseModel):
    answer: str

@app.post("/query", response_model=QueryResponse)
def query_endpoint(
    request_data: QueryRequest,
    user: Optional[dict] = Depends(get_optional_user),
    token: Optional[Any] = Depends(reusable_oauth2)
):
    """
    Executes a query against the RAG pipeline.
    Returns a single clean answer — all retrieval internals are hidden.
    """
    user_id = user.get("user_id") if user else None
    email = user.get("email") if user else None
    role = user.get("role") if user else None

    raw_response = orchestrator.answer_query(
        query=request_data.query,
        answer_satisfied=request_data.answer_satisfied,
        last_chunk_id=request_data.last_chunk_id,
        user_id=user_id,
        email=email,
        role=role
    )

    top_match = raw_response.get("top_match") or {}

    # Derive the single clean answer — blocked queries get the policy message
    if raw_response.get("blocked"):
        answer = "This query violates enterprise security policies."
    elif raw_response.get("answer_found") is False:
        # Added customized fallback answers corresponding to the query's topic context (Add Delivery Location vs Supplier Registration Manual) when no valid answer is retrieved
        if raw_response.get("message"):
            answer = raw_response["message"]
        else:
            q_lower = request_data.query.lower()
            if "delivery" in q_lower or "location" in q_lower:
                answer = "I'm not sure about that specific question. Please refer to the Add Delivery Location User Manual, contact your Reliance Buyer, or reach out to rrsrportal@ril.com for assistance."
            else:
                answer = "I'm not sure about that specific question. Please check the Supplier Registration Manual or contact your Reliance Buyer for assistance. You can also check your registration status at https://supplierregistration.ril.com/"
    else:
        answer = (
            raw_response.get("synthesized_answer")
            or top_match.get("answer_excerpt")
            or "I could not find relevant information in the provided documents."
        )

    return {"answer": answer}


@app.get("/protected-test")
def protected_route_test(
    user: dict = Depends(get_current_user),
    token: Optional[Any] = Depends(reusable_oauth2)
):
    """
    Helper endpoint for verification to ensure auth enforcement works.
    """
    return {"message": "Success", "user": user}


import time
from backend.auth.auth_models import SystemMetric

@app.get("/health")
def health_endpoint(db: Session = Depends(get_db)):
    """
    Exposes system readiness, database connectivity, embedding loading state, and orchestrator health.
    """
    # Every modification includes this explanatory comment:
    # "Added system health diagnostics endpoint to verify database connectivity and retrieval model accessibility"
    status_db = "disconnected"
    try:
        # Querying simple SELECT 1 against active dependency session db instead of raw engine to support database overrides in tests
        db.execute(text("SELECT 1"))
        status_db = "connected"
    except Exception as e:
        import sys
        sys.stderr.write(f"Health DB Check Failure: {e}\n")
        pass

    uptime = time.time() - app.state.startup_time if hasattr(app.state, "startup_time") else 0

    # Retrieve state parameters
    rag_loaded = orchestrator.retrieval_engine is not None
    embedding_ready = orchestrator.retrieval_engine.generator is not None if rag_loaded else False

    is_healthy = (status_db == "connected" and rag_loaded and embedding_ready)

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "database": status_db,
        "rag_loaded": rag_loaded,
        "embedding_model": "loaded" if embedding_ready else "not_loaded",
        "retriever": "ready" if rag_loaded else "not_ready",
        "uptime_seconds": int(uptime)
    }


@app.get("/metrics")
def metrics_endpoint(db: Session = Depends(get_db)):
    """
    Exposes key performance indicators (total queries, success, blocked, OTP volumes, latencies).
    """
    # Every modification includes this explanatory comment:
    # "Added application metrics endpoint using database counters to track latency and OTP counts"
    metrics_records = db.query(SystemMetric).all()
    metrics_dict = {m.metric_name: int(m.metric_value) for m in metrics_records}

    # Fetch average latency from logs table
    avg_latency = 0
    p95_latency = 0
    try:
        from backend.auth.auth_models import QueryLog
        latencies = [log.processing_time_ms for log in db.query(QueryLog.processing_time_ms).all()]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            latencies.sort()
            p95_idx = int(len(latencies) * 0.95)
            p95_latency = latencies[p95_idx] if p95_idx < len(latencies) else latencies[-1]
    except Exception:
        pass

    from backend.auth.auth_models import OTPRequestLimit
    otp_sent = db.query(OTPRequestLimit).count()
    otp_blocked = metrics_dict.get("otp_blocked_count", 0)

    return {
        "queries_total": metrics_dict.get("queries_total", 0),
        "successful_queries": metrics_dict.get("successful_queries", 0),
        "fallback_queries": metrics_dict.get("fallback_queries", 0),
        "avg_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "blocked_queries": metrics_dict.get("blocked_queries", 0),
        "otp_sent": otp_sent,
        "otp_blocked": otp_blocked
    }

