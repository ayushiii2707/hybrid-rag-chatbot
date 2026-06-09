import os
import sys
import math
import json

# Bootstrap Paths
BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))

from sentence_transformers import CrossEncoder

cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))

# Load chunks
with open("/Users/ayushiranjan/Desktop/Chatbot/backend/embeddings/metadata.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

chunks_by_id = {c["chunk_id"]: c for c in chunks}

# Q066 chunk (Step 9: FSSAI Details)
fssai_chunk = chunks_by_id["3b97da58a590c41e2833e6360925ec9dc0349b82e177e1dadba8fbd85a089d57_c27"]

# Q067 chunk (Step 7: Request ID Generation - credentials)
credentials_chunk = chunks_by_id["3953124eac5f11b709b4d0a6e920c14f97f925e38323d78625a3d4dd97c3e16b_c25"]

print("=== Q066: FSSAI Safety License portal link ===")
q066_options = [
    "verification link for safety license of food products",
    "verification link for safety license of food products portal link tips focus fssai gov in fbo search option",
    "verification link for safety license of food products check active inactive status of fssai license portal link",
    "verification link for safety license of food products fssai portal link tips focus fssai gov in"
]
for q in q066_options:
    prob = sigmoid(cross_encoder.predict((q, fssai_chunk["text"])))
    print(f"  Query: '{q}'\n    Prob: {prob:.4f}")

print("\n=== Q067: Credentials ===")
q067_options = [
    "where to get credentials to access the onboarding portal",
    "where to get credentials to access the onboarding portal request id generation login credentials activation email",
    "where to get credentials to access the onboarding portal login credentials auto generated email activation link",
    "where to get credentials to access the onboarding portal receive login credentials post request approved"
]
for q in q067_options:
    prob = sigmoid(cross_encoder.predict((q, credentials_chunk["text"])))
    print(f"  Query: '{q}'\n    Prob: {prob:.4f}")
