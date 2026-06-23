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

@router.post("/send-otp")
def send_otp(request_data: SendOTPRequest, db: Session = Depends(get_db)):
    """
    Generates a secure 6-digit OTP, hashes it, stores it in DB, and emails it.
    """
    now = datetime.now(timezone.utc)

    # Normalize email to lowercase and strip whitespace
    email = request_data.email.strip().lower()

    # 1. Delete all globally expired OTP records to prevent table growth
    db.query(EmailOTP).filter(EmailOTP.expires_at < now).delete(synchronize_session=False)
    db.commit()

    # 2. Rate Limiting Check (1 code per 60 seconds)
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

    # 3. Generate secure 6-digit OTP
    otp = "".join(secrets.choice("0123456789") for _ in range(6))

    # 4. Clean up any existing unverified OTP records for this email
    db.query(EmailOTP).filter(EmailOTP.email == email).delete(synchronize_session=False)
    db.commit()

    # 5. Hash OTP and store in DB
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

    # 7. Send OTP email via SMTP (Production Branch)
    try:
        send_otp_email(email, otp)
    except ValueError as e:
        # Cleanup DB record if email failed so they can immediately retry
        db.delete(db_otp)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Cleanup DB record if email failed so they can immediately retry
        db.delete(db_otp)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )

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
