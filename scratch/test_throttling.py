import os
import sys
from fastapi.testclient import TestClient

# ── Bootstrap Paths ───────────────────────────────────────────────────────────
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKSPACE_DIR)

BACKEND_DIR = os.path.join(WORKSPACE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from backend.main import app

def run_throttling_verification():
    print("=" * 80)
    print("  VERIFYING LIGHTWEIGHT REQUEST THROTTLING / RATE LIMITING")
    print("=" * 80)

    client = TestClient(app)
    
    # Send 15 requests in rapid succession (allowed limit is 15 per 10s)
    print("Sending 15 rapid requests (should be allowed)...")
    for i in range(15):
        resp = client.post("/query", json={"query": "What is the link to the supplier registration portal?"})
        # If rate limit triggers early, that's a failure
        assert resp.status_code == 200, f"Request {i+1} was throttled but should have been allowed!"
        
    print("  ✓ First 15 requests allowed successfully.")

    # Send 16th request (should be throttled)
    print("\nSending 16th request (should be blocked with 429)...")
    resp_throttled = client.post("/query", json={"query": "What is the link to the supplier registration portal?"})
    print(f"  Response Status: {resp_throttled.status_code}")
    print(f"  Response Body  : {resp_throttled.json()}")
    
    assert resp_throttled.status_code == 429, "Rate limit did not trigger for the 16th request!"
    assert "Rate limit exceeded" in resp_throttled.json().get("detail", ""), "Incorrect throttling error message!"
    print("  ✓ Request throttling layer verified. Returned 429 correctly.")

    print("\n" + "=" * 80)
    print("  VERIFICATION SUCCESS: RATE LIMITING ACTIVE AND FUNCTIONAL")
    print("=" * 80)

if __name__ == "__main__":
    run_throttling_verification()
