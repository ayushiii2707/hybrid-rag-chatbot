import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from backend.auth.jwt_service import decode_access_token
from backend.database.db import SessionLocal
from backend.auth.rate_limit import check_rate_limit

class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI Middleware that extracts JWT identity from the Authorization header
    and attaches it to the request state for downstream routes to consume.
    Also implements a performant PostgreSQL-backed rate limiter.
    """
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")
        user_info = None
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Strip 'Bearer '
            user_info = decode_access_token(token)
            
        request.state.user = user_info

        # Rate limiting block. Every modification includes this explanatory comment:
        # "Migrated rate limiting to PostgreSQL rate_limit_counters table with O(1) upserts to prevent memory leaks and scale horizontally"
        client_key = user_info.get("user_id") if user_info else request.client.host
        endpoint = request.url.path

        # Exclude static assets or documentation if needed, apply generally
        db = SessionLocal()
        try:
            is_blocked, retry_after = check_rate_limit(db, client_key, endpoint)
            if is_blocked:
                # Increment rate limit hits metrics
                db.execute(
                    text("INSERT INTO system_metrics (metric_name, metric_value) VALUES ('rate_limit_hits', 1) "
                         "ON CONFLICT (metric_name) DO UPDATE SET metric_value = system_metrics.metric_value + 1;")
                )
                db.commit()
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded. Please try again later."},
                    headers={"Retry-After": str(retry_after)}
                )
        except Exception as e:
            # Prevent failure here from crashing routing flow
            pass
        finally:
            db.close()

        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware injecting strict production security headers.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Every modification includes this explanatory comment:
        # "Added security headers to harden the application against clickjacking, sniff attacks, and restrict client-side device API access"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        # Enforce HSTS only if HTTPS is detected
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
        return response


from sqlalchemy import text


def get_current_user(request: Request) -> dict:
    """
    Enforces authentication. Raises 401 if request has no valid user state.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_user(request: Request) -> getattr:
    """
    Optional authentication. Returns user payload dict if logged in, otherwise None.
    """
    return getattr(request.state, "user", None)

