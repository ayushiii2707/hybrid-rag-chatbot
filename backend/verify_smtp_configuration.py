import os
import sys
import smtplib
import socket
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv

def run_smtp_verification():
    # Load backend env variables
    BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(BACKEND_DIR, ".env")
    load_dotenv(dotenv_path)

    SMTP_EMAIL = os.getenv("SMTP_EMAIL")
    SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = os.getenv("SMTP_PORT", "587")

    # Sanitize inputs
    if SMTP_EMAIL:
        SMTP_EMAIL = SMTP_EMAIL.strip()
    if SMTP_APP_PASSWORD:
        SMTP_APP_PASSWORD = SMTP_APP_PASSWORD.replace(" ", "").strip()
    if SMTP_HOST:
        SMTP_HOST = SMTP_HOST.strip()

    print(f"Loaded credentials from: {dotenv_path}")
    print(f"SMTP Host: {SMTP_HOST}")
    print(f"SMTP Port: {SMTP_PORT}")
    print(f"SMTP Email: {SMTP_EMAIL}")
    print("---------------------------------------")

    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        print("FAIL: SMTP credentials not configured.")
        sys.exit(1)

    try:
        port = int(SMTP_PORT)
    except ValueError:
        print("FAIL: SMTP credentials not configured. SMTP_PORT must be an integer.")
        sys.exit(1)

    # 1. SMTP Connection
    try:
        server = smtplib.SMTP(SMTP_HOST, port, timeout=10.0)
        print("SMTP connection: PASS")
    except (socket.timeout, TimeoutError):
        print("FAIL: SMTP connection timed out.")
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: SMTP connection failed: {str(e)}")
        sys.exit(1)

    # 2. TLS Negotiation
    try:
        server.ehlo()
        if server.has_extn("STARTTLS"):
            server.starttls()
            server.ehlo()
            print("TLS negotiation: PASS")
        else:
            print("FAIL: STARTTLS negotiation failed. Server does not support STARTTLS.")
            server.close()
            sys.exit(1)
    except Exception as e:
        print(f"FAIL: STARTTLS negotiation failed: {str(e)}")
        try:
            server.close()
        except Exception:
            pass
        sys.exit(1)

    # 3. Authentication
    try:
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        print("Authentication: PASS")
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected):
        print("FAIL: Gmail rejected authentication.")
        print("Possible causes:")
        print("- Invalid App Password")
        print("- App Password generated from another account")
        print("- 2-Step Verification disabled")
        try:
            server.close()
        except Exception:
            pass
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: Authentication failed: {str(e)}")
        try:
            server.close()
        except Exception:
            pass
        sys.exit(1)

    # 4. Test Email Delivery
    try:
        subject = "Platform SMTP Verification Test"
        body = "Hello! This is a test email sent by the platform's verify_smtp_configuration.py script to confirm that Gmail SMTP authentication and delivery are fully functional."
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = SMTP_EMAIL
        msg["To"] = SMTP_EMAIL

        server.sendmail(SMTP_EMAIL, [SMTP_EMAIL], msg.as_string())
        print("Test email delivery: PASS")
    except Exception as e:
        print("FAIL: SMTP authenticated successfully but test email delivery failed.")
        print(f"Reason: {str(e)}")
        sys.exit(1)
    finally:
        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass

if __name__ == "__main__":
    run_smtp_verification()
