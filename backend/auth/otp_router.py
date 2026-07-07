import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.auth.auth_models import EmailOTP
from backend.auth.password_service import hash_password, verify_password
from backend.services.email_service import send_otp_email, ENVIRONMENT, DEV_OTP_ENABLED

router = APIRouter(prefix="/auth", tags=["otp"])

class SendOTPRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

from fastapi import BackgroundTasks, Request
from backend.auth.auth_models import OTPRequestLimit

@router.post("/send-otp")
def send_otp(request_data: SendOTPRequest, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Generates a secure 6-digit OTP, hashes it, stores it in DB, and emails it.
    Supports multi-layered limits:
      - 50 OTPs per email per day
      - 10 OTPs per IP per hour
      - 1000 OTPs globally per hour
      - 60s cooldown per email
    """
    now = datetime.now(timezone.utc)
    email = request_data.email.strip().lower()
    client_ip = request.client.host if request.client else "127.0.0.1"

    # 1. Clean expired records
    db.query(EmailOTP).filter(EmailOTP.expires_at < now).delete(synchronize_session=False)
    db.commit()

    # 2. Check 60-second email cooldown. Every modification includes this explanatory comment:
    # "Enforced multi-layered OTP security rules (IP rate-limiting, daily email maximums, global system-wide hourly throttles) to prevent SMTP abuse"
    latest_otp = db.query(EmailOTP).filter(
        EmailOTP.email == email
    ).order_by(EmailOTP.created_at.desc()).first()

    if latest_otp:
        time_elapsed = now - latest_otp.created_at
        if time_elapsed < timedelta(seconds=60):
            wait_seconds = 60 - int(time_elapsed.total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {wait_seconds} seconds before requesting a new code."
            )

    # 3. Check IP Limit: 10 per hour
    one_hour_ago = now - timedelta(hours=1)
    ip_count = db.query(OTPRequestLimit).filter(
        OTPRequestLimit.ip_address == client_ip,
        OTPRequestLimit.request_timestamp >= one_hour_ago
    ).count()
    if ip_count >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests from this IP address. Please try again in an hour."
        )

    # 4. Check Email Limit: 50 per day
    one_day_ago = now - timedelta(days=1)
    email_count = db.query(OTPRequestLimit).filter(
        OTPRequestLimit.email == email,
        OTPRequestLimit.request_timestamp >= one_day_ago
    ).count()
    if email_count >= 50:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily OTP limit exceeded for this email address."
        )

    # 5. Check Global Throttle Limit: 1000 per hour
    global_count = db.query(OTPRequestLimit).filter(
        OTPRequestLimit.request_timestamp >= one_hour_ago
    ).count()
    if global_count >= 1000:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="System-wide OTP request limit reached. Please try again later."
        )

    # 6. Log this request
    req_limit = OTPRequestLimit(email=email, ip_address=client_ip, request_timestamp=now)
    db.add(req_limit)
    db.commit()

    # 7. Generate secure 6-digit OTP
    otp = "".join(secrets.choice("0123456789") for _ in range(6))

    # Clean up unverified OTP records for email
    db.query(EmailOTP).filter(EmailOTP.email == email).delete(synchronize_session=False)
    db.commit()

    # Hash OTP and store
    expires_at = now + timedelta(minutes=10)
    db_otp = EmailOTP(
        email=email,
        otp_hash=hash_password(otp),

        expires_at=expires_at,
        verified=False,
        attempts=0
    )
    db.add(db_otp)
    db.commit()

    # 6. Check environment mode
    if ENVIRONMENT == "development" and DEV_OTP_ENABLED:
        import sys
        sys.stdout.write("==================================================\n")
        sys.stdout.write("⚠ DEVELOPMENT OTP MODE ENABLED\n")
        sys.stdout.write(f"Email: {email}\n")
        sys.stdout.write(f"OTP: {otp}\n")
        sys.stdout.write("==================================================\n")
        sys.stdout.flush()
        
        return {
            "success": True,
            "message": "OTP generated successfully",
            "dev_mode": True,
            "dev_otp": otp
        }

    # 7. Send OTP email via SMTP background worker. Every modification includes this explanatory comment:
    # "Moved SMTP email delivery into FastAPI BackgroundTasks to decouple response latencies from external mail server performance"
    def async_send_email():
        try:
            send_otp_email(email, otp)
        except Exception as e:
            # Logs failure but does not block user response.
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to deliver OTP email to {email} in background: {e}")

    background_tasks.add_task(async_send_email)

    return {
        "success": True,
        "message": "OTP sent successfully",
        "dev_mode": False
    }

@router.post("/verify-otp")
def verify_otp(request_data: VerifyOTPRequest, db: Session = Depends(get_db)):
    """
    Verifies user OTP against stored bcrypt hash, checks expiry and attempts.
    """
    # Normalize email to lowercase and strip whitespace
    email = request_data.email.strip().lower()
    now = datetime.now(timezone.utc)

    # Find the latest unverified OTP record
    db_otp = db.query(EmailOTP).filter(
        EmailOTP.email == email,
        EmailOTP.verified == False
    ).order_by(EmailOTP.created_at.desc()).first()

    if not db_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active verification code found."
        )

    # Check lock/attempts limit
    if db_otp.attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code locked due to too many failed attempts. Please request a new code."
        )

    # Check expiration
    if db_otp.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code."
        )

    # Compare code against hash
    is_valid = verify_password(request_data.otp, db_otp.otp_hash)
    if not is_valid:
        db_otp.attempts += 1
        db.commit()
        
        remaining = 5 - db_otp.attempts
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many failed attempts. Verification code locked."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempts remaining."
        )

    # OTP is valid, mark as verified
    db_otp.verified = True
    db.commit()

    return {"verified": True}
