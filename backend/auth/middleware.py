import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from backend.auth.jwt_service import decode_access_token

class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI Middleware that extracts JWT identity from the Authorization header
    and attaches it to the request state for downstream routes to consume.
    Also implements a lightweight, in-memory per-user/IP rate limiter.
    """
    def __init__(self, app, rate_limit: int = 15, window_seconds: int = 10):
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        self.request_history = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")
        user_info = None
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Strip 'Bearer '
            user_info = decode_access_token(token)
            
        request.state.user = user_info

        # Rate limiting block
        client_key = user_info.get("user_id") if user_info else request.client.host
        now = time.time()
        
        # Keep only timestamps in the current sliding window
        self.request_history[client_key] = [
            t for t in self.request_history[client_key]
            if now - t < self.window_seconds
        ]
        
        if len(self.request_history[client_key]) >= self.rate_limit:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )
            
        self.request_history[client_key].append(now)

        response = await call_next(request)
        return response


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
