import os
import sys
import json

BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))

from query_orchestrator import QueryOrchestrator

orchestrator = QueryOrchestrator()
orchestrator.audit_logger = None

# Let's run and print raw values
query = "guidelines for submitting supplier registration applications"
prep_results = orchestrator.preprocessor.preprocess_query(query)
corrected_q = prep_results["corrected_query"]
print(f"corrected_q: '{corrected_q}'")

# Classify and retrieve
from context_assembler import classify_query_granularity
granularity = classify_query_granularity(corrected_q)
candidates = orchestrator.retrieval_engine.retrieve_best_chunk(corrected_q, top_k=orchestrator.retrieval_top_k)

top_cand = candidates[0] if candidates else None
if top_cand:
    print(f"Top Candidate Score: {top_cand['score']}")
    print(f"Top Candidate Breakdown: {json.dumps(top_cand.get('breakdown', {}), indent=2)}")
    
    # Check conditions
    semantic_score = top_cand.get("breakdown", {}).get("semantic", 0.0)
    keyword_score = top_cand.get("breakdown", {}).get("keyword", 0.0)
    applied_mismatch_penalty = top_cand.get("breakdown", {}).get("intent_mismatch_penalty", 0.0) < 0.0
    
    is_weak_semantic = (semantic_score < 0.72)
    is_high_keyword = (keyword_score > 0.90)
    is_duplicate_query = ("duplicate" in corrected_q.lower() or "exist" in corrected_q.lower() or "uniqueness" in corrected_q.lower())
    
    print(f"is_weak_semantic: {is_weak_semantic} (semantic_score={semantic_score})")
    print(f"is_high_keyword: {is_high_keyword} (keyword_score={keyword_score})")
    print(f"is_duplicate_query: {is_duplicate_query}")
    print(f"applied_mismatch_penalty: {applied_mismatch_penalty}")
    print(f"Condition 1 (is_weak_semantic and is_high_keyword): {is_weak_semantic and is_high_keyword}")
    print(f"Condition 2 (applied_mismatch_penalty and is_duplicate_query): {applied_mismatch_penalty and is_duplicate_query}")
    print(f"Will trigger rejection: {(is_weak_semantic and is_high_keyword) or (applied_mismatch_penalty and is_duplicate_query)}")

print("\nRunning complete answer_query call...")
res = orchestrator.answer_query(query)
print(f"answer_found: {res.get('answer_found')}")
print(f"confidence: {res.get('confidence')}")
