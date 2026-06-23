import sys
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# Bootstrap paths
WORKSPACE_DIR = "/Users/ayushiranjan/Desktop/Chatbot"
sys.path.insert(0, WORKSPACE_DIR)

from fastapi.testclient import TestClient
from backend.main import app
from backend.database.db import SessionLocal
from backend.auth.auth_models import EmailOTP, User
from backend.auth.password_service import verify_password

def run_dual_mode_tests():
    client = TestClient(app)
    db = SessionLocal()
    
    print("=== Running Dual-Mode OTP Verification Tests ===")

    test_email = "test_dual_mode@example.com"
    db.query(EmailOTP).filter(EmailOTP.email == test_email).delete()
    db.query(User).filter(User.email == test_email).delete()
    db.commit()

    # =========================================================================
    # PART 1: DEVELOPMENT MODE TESTS
    # =========================================================================
    print("\n--- [PART 1] Testing Development Mode ---")
    
    # Mock ENVIRONMENT=development and DEV_OTP_ENABLED=true at the module level
    with patch("backend.auth.otp_router.ENVIRONMENT", "development"), \
         patch("backend.auth.otp_router.DEV_OTP_ENABLED", True):
         
        # 1. Verify OTP generation succeeds without SMTP & returns dev_otp
        res = client.post("/auth/send-otp", json={"email": test_email})
        assert res.status_code == 200
        data = res.json()
        assert data["dev_mode"] is True
        dev_otp = data["dev_otp"]
        assert len(dev_otp) == 6
        print(f"  OTP generated: PASS (dev_otp={dev_otp})")

        # 2. Verify bcrypt hash stored in DB matches the generated code
        db_otp = db.query(EmailOTP).filter(EmailOTP.email == test_email).first()
        assert db_otp is not None
        assert db_otp.verified is False
        assert db_otp.attempts == 0
        assert verify_password(dev_otp, db_otp.otp_hash) is True
        print("  Bcrypt storage check: PASS")

        # 3. Verify cooldown (cooldown should still be active)
        res_spam = client.post("/auth/send-otp", json={"email": test_email})
        assert res_spam.status_code == 429
        print("  Cooldown check: PASS (429 returned on rapid send request)")

        # 4. Verify lockout (5 wrong attempts locks it)
        # Fast-forward rate limit inside DB for lockout test by deleting and requesting a new code
        db.query(EmailOTP).filter(EmailOTP.email == test_email).delete()
        db.commit()
        
        # Send new OTP
        res_new = client.post("/auth/send-otp", json={"email": test_email})
        dev_otp_new = res_new.json()["dev_otp"]
        
        db_otp_new = db.query(EmailOTP).filter(EmailOTP.email == test_email).first()
        for attempt in range(1, 6):
            res_wrong = client.post("/auth/verify-otp", json={"email": test_email, "otp": "000000"})
            assert res_wrong.status_code == 400
        
        # Verify 6th verification with correct code fails due to lockout
        res_correct_lock = client.post("/auth/verify-otp", json={"email": test_email, "otp": dev_otp_new})
        assert res_correct_lock.status_code == 400
        assert "locked" in res_correct_lock.json()["detail"]
        print("  Brute force lockout check: PASS (5 failures locked the OTP)")

        # 5. Verify cleanup (globally expired cleanup)
        # Manually create an expired OTP record
        expired_email = "expired_test@example.com"
        db.query(EmailOTP).filter(EmailOTP.email == expired_email).delete()
        db_expired = EmailOTP(
            email=expired_email,
            otp_hash="dummy_hash",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            verified=False,
            attempts=0
        )
        db.add(db_expired)
        db.commit()
        
        # Trigger send-otp for developer which should delete globally expired records
        db.query(EmailOTP).filter(EmailOTP.email == test_email).delete()
        db.commit()
        
        res_cleanup = client.post("/auth/send-otp", json={"email": test_email})
        assert res_cleanup.status_code == 200
        dev_otp_clean = res_cleanup.json()["dev_otp"]
        
        db_expired_check = db.query(EmailOTP).filter(EmailOTP.email == expired_email).first()
        assert db_expired_check is None
        print("  Expired records cleanup check: PASS")

        # 6. Verify registration verification enforcement and cleanup
        # Verify OTP first
        res_v = client.post("/auth/verify-otp", json={"email": test_email, "otp": dev_otp_clean})
        assert res_v.status_code == 200
        
        # Register
        res_r = client.post("/register", json={"email": test_email, "password": "Password123!"})
        assert res_r.status_code == 201
        print("  Registration: PASS")

        # Verify OTP record is deleted after successful registration
        db_otp_del = db.query(EmailOTP).filter(EmailOTP.email == test_email).first()
        assert db_otp_del is None
        print("  OTP record deletion after registration check: PASS")

        # Cleanup user
        db.query(User).filter(User.email == test_email).delete()
        db.commit()

    # =========================================================================
    # PART 2: PRODUCTION MODE TESTS
    # =========================================================================
    print("\n--- [PART 2] Testing Production Mode ---")
    
    # Mock ENVIRONMENT=production and DEV_OTP_ENABLED=false
    with patch("backend.auth.otp_router.ENVIRONMENT", "production"), \
         patch("backend.auth.otp_router.DEV_OTP_ENABLED", False):
         
        # 1. Verify missing SMTP credentials fail the send-otp flow (SMTP mandatory)
        # Mock SMTP settings to empty
        with patch("backend.services.email_service.SMTP_EMAIL", ""), \
             patch("backend.services.email_service.SMTP_APP_PASSWORD", ""):
            res_prod_fail = client.post("/auth/send-otp", json={"email": test_email})
            assert res_prod_fail.status_code == 400
            assert "SMTP credentials not configured" in res_prod_fail.json()["detail"]
            print("  SMTP credentials enforcement check: PASS")

        # 2. Verify OTP is never returned in response under production mode
        # Mock correct SMTP credentials at the module level, but mock sendmail to bypass transmission
        captured_production_otp = []
        def mock_sendmail_interceptor(recipient_email, otp):
            captured_production_otp.append(otp)

        with patch("backend.auth.otp_router.send_otp_email", side_effect=mock_sendmail_interceptor), \
             patch("backend.services.email_service.SMTP_EMAIL", "dummy@gmail.com"), \
             patch("backend.services.email_service.SMTP_APP_PASSWORD", "dummy"):
             
             res_prod_ok = client.post("/auth/send-otp", json={"email": test_email})
             assert res_prod_ok.status_code == 200
             data_prod = res_prod_ok.json()
             assert "dev_otp" not in data_prod
             assert data_prod["dev_mode"] is False
             assert data_prod["success"] is True
             print("  OTP exposure prevention check: PASS (OTP code not leaked in response)")

    print("\n=== All Dual-Mode OTP Verification Tests Passed Successfully! ===")

if __name__ == "__main__":
    run_dual_mode_tests()
