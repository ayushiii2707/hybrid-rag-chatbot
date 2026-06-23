import os
import smtplib
import socket
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv

# Load environment variables from backend/.env
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(BACKEND_DIR, ".env")
load_dotenv(dotenv_path)

# Read SMTP configuration from environment variables
SMTP_EMAIL = os.getenv("SMTP_EMAIL").strip() if os.getenv("SMTP_EMAIL") else None
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD").replace(" ", "").strip() if os.getenv("SMTP_APP_PASSWORD") else None
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# Read Environment settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").strip().lower()
DEV_OTP_ENABLED = os.getenv("DEV_OTP_ENABLED", "false").strip().lower() == "true"

def send_otp_email(recipient_email: str, otp: str) -> None:
    """
    Sends a 6-digit verification code to the recipient email using Gmail SMTP.
    Raises ValueError if configuration is missing, and RuntimeError for TLS/connection/auth failures.
    """
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise ValueError("SMTP credentials not configured. Please check SMTP_EMAIL and SMTP_APP_PASSWORD.")

    # Create SMTP message
    subject = "Platform Verification Code"
    body = (
        f"Hello,\n\n"
        f"Your verification code is:\n\n"
        f"{otp}\n\n"
        f"This code expires in 10 minutes.\n\n"
        f"If you did not request this verification, please ignore this email.\n\n"
        f"Regards,\n"
        f"Platform Team"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = SMTP_EMAIL
    msg["To"] = recipient_email

    # Connect to SMTP server using TLS
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10.0)
    except (socket.timeout, TimeoutError):
        raise RuntimeError("SMTP connection timeout. Check your network or SMTP_HOST/SMTP_PORT configuration.")
    except Exception as e:
        raise RuntimeError(f"SMTP connection failed: {str(e)}")

    try:
        server.ehlo()
        if server.has_extn("STARTTLS"):
            server.starttls() # Enable TLS
            server.ehlo()
        else:
            raise RuntimeError("SMTP server does not support STARTTLS.")
    except Exception as e:
        try:
            server.close()
        except Exception:
            pass
        raise RuntimeError(f"TLS negotiation failed: {str(e)}")

    try:
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
    except smtplib.SMTPAuthenticationError as e:
        try:
            server.close()
        except Exception:
            pass
        raise RuntimeError("Gmail authentication failed. Gmail rejected the login attempt. Check your Gmail App Password configuration.")
    except Exception as e:
        try:
            server.close()
        except Exception:
            pass
        raise RuntimeError(f"SMTP login failed: {str(e)}")

    try:
        server.sendmail(SMTP_EMAIL, [recipient_email], msg.as_string())
    except Exception as e:
        raise RuntimeError(f"Email delivery failed: {str(e)}")
    finally:
        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass
