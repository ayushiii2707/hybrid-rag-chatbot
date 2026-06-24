import sys
sys.path.append('/Users/ayushiranjan/Desktop/Chatbot/backend')
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
response = client.post("/query", json={"query": "good morning how r u"})
print("Status Code:", response.status_code)
print("JSON Response:", response.json())
