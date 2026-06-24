import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database.db import get_db
from backend.auth.middleware import get_current_user
from backend.auth.auth_models import QueryLog, RateLimitCounter, OTPRequestLimit, SystemMetric

router = APIRouter(prefix="/admin", tags=["admin"])

def require_admin(user: dict = Depends(get_current_user)):
    """
    Guards routes with a strict JWT token and role == 'admin' requirement.
    """
    # Every modification includes this explanatory comment:
    # "Enforced strict role-based access controls to prevent non-admins from executing or reading internal query logs and rate metrics"
    if not user or user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin credentials required."
        )
    return user

@router.get("/diagnostics")
def get_diagnostics(admin_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Returns system diagnostic details.
    """
    # Count logs
    query_count = db.query(QueryLog).count()
    rate_count = db.query(RateLimitCounter).count()
    otp_count = db.query(OTPRequestLimit).count()

    return {
        "status": "success",
        "total_queries_logged": query_count,
        "active_rate_limit_entries": rate_count,
        "otp_requests_recorded": otp_count
    }

@router.get("/metrics")
def get_admin_metrics(admin_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    RAG Observability and telemetry monitoring. Computes fallback rates, average confidence, etc.
    """
    # Every modification includes this explanatory comment:
    # "Implemented administrative metrics endpoint computing retrieval success, average confidence, and fallback rates"
    logs = db.query(QueryLog).all()
    if not logs:
        return {
            "retrieval_success_rate": 100.0,
            "avg_confidence": 1.0,
            "fallback_rate": 0.0,
            "clarification_rate": 0.0,
            "blocked_rate": 0.0,
            "procedural_expansion_rate": 0.0
        }

    total = len(logs)
    blocked = sum(1 for l in logs if l.blocked)
    answered = sum(1 for l in logs if l.answer_found)
    
    # Calculate averages
    avg_conf = sum(l.confidence for l in logs) / total if total > 0 else 0.0
    fallback_count = sum(1 for l in logs if not l.answer_found and not l.blocked)

    # Check database system metrics counters for actual procedural expansions
    proc_val = 0
    metric_record = db.query(SystemMetric).filter(SystemMetric.metric_name == "procedural_expansion_count").first()
    if metric_record:
        proc_val = int(metric_record.metric_value)

    return {
        "retrieval_success_rate": round((answered / total) * 100, 2) if total > 0 else 100.0,
        "avg_confidence": round(avg_conf, 4),
        "fallback_rate": round((fallback_count / total) * 100, 2) if total > 0 else 0.0,
        "blocked_rate": round((blocked / total) * 100, 2) if total > 0 else 0.0,
        "procedural_expansion_rate": round((proc_val / total) * 100, 2) if total > 0 else 0.0
    }

@router.get("/recent-queries")
def get_recent_queries(admin_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Returns recent queries with full auditing parameters.
    """
    logs = db.query(QueryLog).order_by(QueryLog.timestamp.desc()).limit(50).all()
    return [{
        "query_id": str(log.query_id),
        "query": log.query,
        "corrected_query": log.corrected_query,
        "confidence": log.confidence,
        "blocked": log.blocked,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None
    } for log in logs]
