from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.auth.auth_models import User
from backend.auth.password_service import hash_password, verify_password

def register_user(db: Session, email: str, password_raw: str, role: str = "vendor") -> User:
    """
    Registers a new user after verifying that the email is not already registered.
    """
    normalized_email = email.strip().lower()
    
    # Check for duplicate email
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password and save new user
    hashed = hash_password(password_raw)
    db_user = User(
        email=normalized_email,
        hashed_password=hashed,
        role=role,
        status="active"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password_raw: str) -> User:
    """
    Authenticates user credentials and returns the User model instance if valid.
    """
    normalized_email = email.strip().lower()
    
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    if not verify_password(password_raw, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Record last login timestamp
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user
