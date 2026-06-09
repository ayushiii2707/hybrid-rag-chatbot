import sys
import os
import json

# Bootstrap Paths
BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))

from query_orchestrator import QueryOrchestrator
from context_assembler import classify_query_granularity

queries = [
    # Purpose Queries
    ("What is the Add Delivery Location process for?", "purpose"),
    ("What is the Supplier Registration Portal used for?", "purpose"),
    ("Why do we have a Vendor Onboarding process?", "purpose"),
    ("What is the purpose of the New Merchandise Vendor Registration?", "purpose"),
    
    # Overview Queries
    ("Explain the onboarding flow for new vendors", "overview"),
    ("Can you give me an overview of the Add Delivery Location process?", "overview"),
    ("Describe the steps involved in registering as a supplier", "overview"),
    ("What is the general workflow for setting up a profile?", "overview"),
    
    # Eligibility Queries
    ("Who is eligible to register as a merchandise supplier?", "eligibility"),
    ("What are the eligibility criteria for adding a new delivery location?", "eligibility"),
    ("Which vendors are required to upload a UDYAM certificate?", "eligibility"),
    ("Are trading suppliers allowed to register on the portal?", "eligibility"),
    
    # Factual Queries
    ("Where is the link to the supplier registration portal?", "factual"),
    ("What is the format for GSTIN registration?", "factual"),
    ("What is the active status link for FSSAI checking?", "factual"),
    ("What is the maximum limit for file upload size?", "factual"),
    
    # Procedural Queries
    ("How do I add a delivery location?", "procedural"),
    ("What are the steps to upload my PAN details?", "procedural"),
    ("How can I register as a new merchandise supplier?", "procedural"),
    ("Procedure to submit bank validation details", "procedural")
]

print("Initializing QueryOrchestrator...")
orchestrator = QueryOrchestrator()
print("Initialized successfully.")

results_log = []

for idx, (q, category) in enumerate(queries, 1):
    print(f"\nProcessing Query {idx}/20: '{q}' ({category})")
    
    # Preprocess
    prep_results = orchestrator.preprocessor.preprocess_query(q)
    corrected_q = prep_results["corrected_query"]
    retrieval_q = orchestrator.preprocessor.expand_synonyms(corrected_q)
    
    # Classify
    granularity = classify_query_granularity(corrected_q)
    is_procedural = granularity in ("procedural", "workflow")
    
    # Retrieve Candidates (retrieve top 10)
    if is_procedural:
        candidates = orchestrator.retrieval_engine.retrieve_candidate_chunks(
            retrieval_q, top_k=10, original_query=corrected_q
        )
    else:
        candidates = orchestrator.retrieval_engine.retrieve_best_chunk(
            retrieval_q, top_k=10, original_query=corrected_q
        )
        
    query_res = {
        "index": idx,
        "query": q,
        "corrected_query": corrected_q,
        "category": category,
        "granularity": granularity,
        "candidates": []
    }
    
    for rank, cand in enumerate(candidates, 1):
        metadata = cand.get("metadata", {})
        bd = cand.get("breakdown", {})
        cand_info = {
            "rank": rank,
            "chunk_id": cand["chunk_id"],
            "source_file": metadata.get("source_file"),
            "page_number": metadata.get("page_number"),
            "section_title": metadata.get("section_title"),
            "text_snippet": cand["text"][:120].replace("\n", " ") + "...",
            "score": cand["score"],
            "faiss_score": cand.get("raw_similarity", bd.get("faiss_similarity", 0.0)),
            "bm25_score": bd.get("keyword", 0.0),
            "ce_score": bd.get("cross_encoder_score", 0.0),
            "alignment": bd.get("alignment", 1.0),
            "sufficiency": bd.get("sufficiency", 1.0),
            "answerability": bd.get("answerability", 0.0)
        }
        query_res["candidates"].append(cand_info)
        
    results_log.append(query_res)

# Write results to output JSON file for processing
output_path = "/Users/ayushiranjan/Desktop/Chatbot/scratch/ranking_audit_raw.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results_log, f, indent=2)
print(f"\nAudit completed. Raw results written to {output_path}")
