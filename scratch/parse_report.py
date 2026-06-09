import json

with open("backend/evaluation/benchmark_report.json", "r") as f:
    report = json.load(f)

failures = report["failure_cases_summary"]

# Let's read details of all failures to map retrieved chunks
# We need to read from a run log or results array. Since run_benchmark.py doesn't write all runs to json,
# let's run the diagnostics for the failures directly or search the json report.
# Wait, let's load all results. We can modify run_benchmark.py to save the full results array or we can just parse
# the failure list in benchmark_report.json. Let's check what fields are in failure_cases_summary:
# "query_id", "query_text", "category", "expected_behavior", "final_action", "confidence_score", "latency_ms", "reason"
# Wait, did we save retrieved_chunks in failure_cases_summary? Let's check benchmark_report.json.
# In run_benchmark.py:
# failure_cases_summary.append({
#     "query_id": r["query_id"],
#     "query_text": r["query_text"],
#     "category": r["category"],
#     "expected_behavior": r["expected_behavior"],
#     "final_action": r["final_action"],
#     "confidence_score": r["confidence_score"],
#     "latency_ms": r["latency_ms"],
#     "reason": r["failure_reason"]
# })
# Wait, we did not include retrieved_chunks in the failure case dictionary, but we can easily run a diagnostic script
# to fetch them. Let's do that!

# Let's write a script to re-run only the failed queries and print their details including retrieved chunks.
# This will give us the retrieved chunks for failed synonym queries, escaping malicious queries, and failing procedural queries.

import sys
import os

BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))

from query_orchestrator import QueryOrchestrator
orchestrator = QueryOrchestrator()
orchestrator.audit_logger = None

failed_ids = [f["query_id"] for f in failures]

print("="*80)
print("DIAGNOSTICS FOR BENCHMARK FAILURES")
print("="*80)

# Load CSV
import csv
csv_path = "backend/evaluation/benchmark_queries.csv"
queries = {}
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        queries[row["query_id"]] = row

print("\n--- SYNONYM FAILURES DETAILS ---")
for fid in sorted(failed_ids):
    q_item = queries[fid]
    if q_item["category"] != "synonym":
        continue
    
    res = orchestrator.answer_query(q_item["query_text"])
    top = res.get("top_match")
    top_chunk = top.get("chunk_id") if top else "None"
    
    # Map final action
    blocked = res.get("blocked", False)
    answer_found = res.get("answer_found", False)
    synthesized_answer = res.get("synthesized_answer", "")
    message = res.get("message", "")
    
    if blocked:
        action = "block_query"
    elif answer_found:
        action = "retrieve_answer"
    elif "Did you mean:" in synthesized_answer or "Did you mean:" in message:
        action = "suggest_query"
    else:
        action = "low_confidence_reject"
        
    print(f"ID: {fid} | Query: '{q_item['query_text']}'")
    print(f"  Confidence: {res.get('confidence'):.4f} | Action: {action} | Top Chunk: {top_chunk}")

print("\n--- ESCAPING MALICIOUS QUERIES ---")
for fid in sorted(failed_ids):
    q_item = queries[fid]
    if q_item["category"] != "malicious":
        continue
    
    res = orchestrator.answer_query(q_item["query_text"])
    print(f"ID: {fid} | Query: '{q_item['query_text']}'")
    print(f"  Confidence: {res.get('confidence'):.4f} | Action: low_confidence_reject (Not Blocked)")

print("\n--- FAILING PROCEDURAL QUERIES ---")
for fid in sorted(failed_ids):
    q_item = queries[fid]
    if q_item["category"] != "procedural":
        continue
    
    res = orchestrator.answer_query(q_item["query_text"])
    print(f"ID: {fid} | Query: '{q_item['query_text']}'")
    print(f"  Confidence: {res.get('confidence'):.4f}")
    print(f"  Procedural Expansion: {res.get('procedural_expansion')}")
    print(f"  Expansion Reason: {res.get('expansion_reason')}")
    print(f"  Procedure Length: {res.get('procedure_length')}")
    print(f"  Full Procedure Returned: {res.get('full_procedure_returned')}")

print("\n--- CONFIDENCE REJECTIONS (CONFIDENCE > 0.55 BUT REJECTED) ---")
# Let's search all failures for this condition
for fid in sorted(failed_ids):
    q_item = queries[fid]
    res = orchestrator.answer_query(q_item["query_text"])
    confidence = res.get("confidence", 0.0)
    answer_found = res.get("answer_found", False)
    if confidence >= 0.55 and not answer_found:
        print(f"ID: {fid} | Query: '{q_item['query_text']}' | Category: {q_item['category']}")
        print(f"  Confidence: {confidence:.4f} | Answer Found: {answer_found}")
        
