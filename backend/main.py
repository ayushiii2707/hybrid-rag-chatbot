import os
import sys
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer
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

from backend.database.db import engine, Base, get_db
from backend.auth.auth_models import User
from backend.auth.auth_service import register_user, authenticate_user
from backend.auth.jwt_service import create_access_token
from backend.auth.middleware import JWTAuthMiddleware, get_optional_user, get_current_user
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
        import sys
        sys.stderr.write(f"Warning: Failed to run security_reason schema migration: {e}\n")
        
    yield

# Initialize FastAPI with metadata
app = FastAPI(
    title="Platform RAG Chatbot API",
    description="Enterprise Multi-User RAG Platform Foundation",
    version="1.0.0",
    lifespan=lifespan
)

# Register JWT Middleware
app.add_middleware(JWTAuthMiddleware)

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
    """
    db_user = register_user(
        db=db,
        email=request_data.email,
        password_raw=request_data.password,
        role=request_data.role
    )
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
    db_user = authenticate_user(
        db=db,
        email=request_data.email,
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
