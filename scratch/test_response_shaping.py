import os
import sys

# Bootstrap path
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKSPACE_DIR)
sys.path.insert(0, os.path.join(WORKSPACE_DIR, "backend"))

from fastapi.testclient import TestClient
from backend.main import app

def test_response_shaping():
    print("=" * 80)
    print("  PRODUCTION RESPONSE SHAPING VERIFICATION")
    print("=" * 80)

    client = TestClient(app)

    # 1. Execute query
    query_text = "What is the link to the supplier registration portal?"
    print(f"Sending query: '{query_text}'")
    response = client.post(
        "/query",
        json={"query": query_text}
    )
    
    assert response.status_code == 200, f"Query endpoint failed with status {response.status_code}!"
    response_json = response.json()
    
    # 2. Check keys
    actual_keys = set(response_json.keys())
    expected_keys = {
        "query",
        "corrected_query",
        "query_granularity",
        "answer_found",
        "confidence",
        "confidence_band",
        "synthesized_answer",
        "source_file",
        "page_number",
        "blocked",
        "risk_level",
        "message"
    }

    print("\nReturned Keys:")
    for k in sorted(actual_keys):
        print(f"  - {k}: {response_json[k]}")

    # Assert exactly matches the expected set
    extra_keys = actual_keys - expected_keys
    missing_keys = expected_keys - actual_keys
    
    assert len(extra_keys) == 0, f"API leaked internal fields: {extra_keys}"
    assert len(missing_keys) == 0, f"API missing required fields: {missing_keys}"
    
    print("\n" + "=" * 80)
    print("  VERIFICATION SUCCESS: ALL API RESPONSES CORRECTLY SHAPED FOR PRODUCTION")
    print("=" * 80)

if __name__ == "__main__":
    test_response_shaping()
