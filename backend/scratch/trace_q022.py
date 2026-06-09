import os
import sys

# Bootstrap Paths
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "security"))

from query_orchestrator import QueryOrchestrator
from query_preprocessor import QueryPreprocessor

# Print raw candidates
preprocessor = QueryPreprocessor()
print("=== PREPROCESSOR TRACE ===")
res = preprocessor.preprocess_query("how to input micr code in bank details")
print("Preprocessed:", res)
expanded = preprocessor.expand_synonyms(res["corrected_query"])
print("Expanded:", expanded)

print("\n=== RETRIEVAL TRACE ===")
orchestrator = QueryOrchestrator()
candidates = orchestrator.retrieval_engine.retrieve_candidate_chunks(expanded)
for c in candidates:
    print(f"Chunk ID: {c['chunk_id']}, Score: {c['score']:.4f}")
    if "breakdown" in c:
        print("  Breakdown:", c["breakdown"])

print("\n=== ORCHESTRATOR TRACE ===")
orchestrator = QueryOrchestrator()
orchestrator.audit_logger = None
ans = orchestrator.answer_query("how to input micr code in bank details")
import json
print(json.dumps(ans, indent=2))
