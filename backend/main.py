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
load_dotenv(dotenv_path)

from backend.database.db import engine, Base, get_db, SessionLocal
from backend.auth.auth_models import User, EmailOTP
from backend.auth.auth_service import register_user, authenticate_user
from backend.auth.jwt_service import create_access_token
from backend.auth.middleware import JWTAuthMiddleware, get_optional_user, get_current_user
from backend.chat_router import router as chat_router
from backend.auth.otp_router import router as otp_router
from query_orchestrator import QueryOrchestrator

# ── Lifespan for Startup and Shutdown Events ──────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    Base.metadata.create_all(bind=engine)
    
    # Run schema migration dynamically to ensure security_reason column exists
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS security_reason TEXT;"))
            conn.commit()
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to run security_reason schema migration: {e}\n")

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

    yield

# Initialize FastAPI with metadata
app = FastAPI(
    title="Platform RAG Chatbot API",
    description="Enterprise Multi-User RAG Platform Foundation",
    version="1.0.0",
    lifespan=lifespan
)

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
    elif raw_response.get("answer_found") is False and raw_response.get("message"):
        answer = raw_response["message"]
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
