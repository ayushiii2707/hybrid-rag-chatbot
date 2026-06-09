import os
import sys
import re
import json

BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))

from query_orchestrator import QueryOrchestrator

SYNONYM_RULES = [
    ("supplier registration", "vendor registration")
]

def expand_synonyms(query: str) -> str:
    query_lower = query.lower()
    expanded_terms = []
    for term, syn in SYNONYM_RULES:
        pattern = r'\b' + re.escape(term) + r'\b'
        if re.search(pattern, query_lower):
            if not re.search(r'\b' + re.escape(syn) + r'\b', query_lower) and syn not in expanded_terms:
                expanded_terms.append(syn)
    if expanded_terms:
        return query + " " + " ".join(expanded_terms)
    return query

orchestrator = QueryOrchestrator()
orchestrator.audit_logger = None

# Run with expansion
query = "guidelines for submitting supplier registration applications"
expanded_q = expand_synonyms(query)
print(f"Expanded Query: '{expanded_q}'")

res = orchestrator.answer_query(expanded_q)
print("=" * 60)
print(f"RESULTS WITH SYNONYM EXPANSION")
print("=" * 60)
print(f"answer_found : {res.get('answer_found')}")
print(f"confidence   : {res.get('confidence')}")
if res.get("top_match"):
    top = res["top_match"]
    print(f"top_match ID : {top.get('chunk_id')}")
    print(f"top score    : {top.get('score')}")
    print(f"breakdown    : {json.dumps(top.get('breakdown', {}), indent=2)}")
else:
    print("top_match is None")
print("=" * 60)
