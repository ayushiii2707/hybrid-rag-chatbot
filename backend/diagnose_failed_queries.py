"""
Diagnostic script for the 21 failed Dataset 1 queries.
Run from: /Users/ayushiranjan/Desktop/Chatbot/backend/
Usage: python3 diagnose_failed_queries.py
"""

import os, sys, json, logging, re

# ── Bootstrap paths ──────────────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "logging"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "security"))

logging.basicConfig(level=logging.WARNING)  # suppress INFO noise

QUERIES = [
    "What format should the UDYAM certificate be uploaded in?",
    "How can I verify my UDYAM number?",
    "check UDYAM status",
    "UDYAM From and To dates",
    "address proof for no GST",
    "GSTIN certificate upload",
    "GSTIN state validation",
    "more than one GSTIN same state",
    "technical issue contact",
    "download bank template",
    "FSSAI verification link",
    "FSSAI expiry date",
    "FSSAI document upload",
    "UDYAM file type",
    "UDYAM verification link",
    "MSME validity period",
    "contact details rules",
    "multiple GSTIN scenario",
    "GSTIN editing",
    "PAN name Y flag",
    "vendor category selection",
]

print("Loading orchestrator (this takes ~30s)...")
from query_engine.query_orchestrator import QueryOrchestrator
from query_engine.query_preprocessor import QueryPreprocessor

orch = QueryOrchestrator()
prep = QueryPreprocessor()

# ── Helper: truncate chunk text for display ──────────────────────────────────
def trunc(t, n=160):
    t = (t or "").replace("\n", " ").strip()
    return t[:n] + "..." if len(t) > n else t

# ── Helper: fetch raw chunk text by ID ──────────────────────────────────────
def get_chunk_text(chunk_id):
    c = orch.retrieval_engine.chunks_by_id.get(chunk_id)
    return c.get("text", "") if c else ""

# ── Run diagnostics ──────────────────────────────────────────────────────────
results = []

for query in QUERIES:
    print(f"\n{'='*80}")
    print(f"QUERY: {query}")
    print("="*80)

    # Step 1 – Preprocessing
    prep_res = prep.preprocess_query(query)
    corrected_q = prep_res["corrected_query"]
    expanded_q  = prep.expand_synonyms(corrected_q)

    print(f"  Corrected  : {corrected_q}")
    print(f"  Expanded   : {expanded_q[:200]}")

    # Step 2 – Check if suggestions layer fires (ambiguity trap)
    from query_engine.context_assembler import classify_query_granularity
    granularity = classify_query_granularity(corrected_q)
    is_suggestion, sugg, sugg_reason = orch._evaluate_query_suggestions(corrected_q)
    print(f"  Granularity: {granularity}")
    print(f"  Suggestion triggered: {is_suggestion}  reason='{sugg_reason}'")

    # Step 3 – Retrieval (bypass full pipeline to get raw candidates + scores)
    retriever = orch.retrieval_engine
    is_procedural = granularity in ("procedural", "workflow")
    if is_procedural:
        candidates = retriever.retrieve_candidate_chunks(expanded_q, top_k=5, original_query=corrected_q)
    else:
        candidates = retriever.retrieve_best_chunk(expanded_q, top_k=5, original_query=corrected_q)

    print(f"\n  Top-{len(candidates)} candidates after full reranking:")
    for i, c in enumerate(candidates):
        bd = c.get("breakdown", {})
        print(f"    [{i+1}] chunk_id={c['chunk_id']}  score={c['score']:.4f}")
        print(f"          faiss={bd.get('faiss_similarity', c.get('raw_similarity', 0)):.4f}  "
              f"ce={bd.get('cross_encoder_score', 0):.4f}  bm25={bd.get('keyword', 0):.4f}  "
              f"semantic={bd.get('semantic', 0):.4f}")
        print(f"          text: {trunc(c.get('text',''), 200)}")

    # Step 4 – Full orchestrator answer
    answer_res = orch.answer_query(query)
    final_answer = answer_res.get("synthesized_answer") or answer_res.get("message") or ""
    answer_found = answer_res.get("answer_found", False)
    confidence   = answer_res.get("confidence", 0.0)
    top_match    = answer_res.get("top_match") or {}
    top_chunk_id = top_match.get("chunk_id", "N/A")

    print(f"\n  answer_found={answer_found}  confidence={confidence:.4f}  top_chunk={top_chunk_id}")
    print(f"  FINAL ANSWER: {trunc(final_answer, 300)}")

    # Step 5 – Keyword search: which chunk actually contains the answer?
    # We do a naive keyword scan across all corpus chunks to find the best matching chunk
    query_kws = [w.lower() for w in re.sub(r'[^a-z0-9\s]','', corrected_q.lower()).split() if len(w) > 3]
    best_kw_chunk_id, best_kw_score, best_kw_snippet = None, 0, ""
    for c in retriever.keyword_ranker.chunks:
        txt = c.get("text","").lower()
        score = sum(1 for kw in query_kws if kw in txt)
        if score > best_kw_score:
            best_kw_score = score
            best_kw_chunk_id = c["chunk_id"]
            best_kw_snippet = trunc(c.get("text",""), 200)

    print(f"\n  Best keyword-matching corpus chunk: {best_kw_chunk_id}  (kw_hits={best_kw_score})")
    print(f"  Snippet: {best_kw_snippet}")

    results.append({
        "query": query,
        "corrected": corrected_q,
        "expanded": expanded_q[:300],
        "granularity": granularity,
        "suggestion_triggered": is_suggestion,
        "suggestion_reason": sugg_reason,
        "top_candidates": [
            {
                "rank": i+1,
                "chunk_id": c["chunk_id"],
                "score": round(c["score"], 4),
                "faiss": round(c.get("breakdown", {}).get("faiss_similarity", c.get("raw_similarity", 0)), 4),
                "ce": round(c.get("breakdown", {}).get("cross_encoder_score", 0), 4),
                "bm25": round(c.get("breakdown", {}).get("keyword", 0), 4),
                "text_snippet": trunc(c.get("text", ""), 200),
            }
            for i, c in enumerate(candidates)
        ],
        "answer_found": answer_found,
        "confidence": round(confidence, 4),
        "top_chunk_id": top_chunk_id,
        "final_answer": final_answer[:400],
        "best_kw_chunk": best_kw_chunk_id,
        "best_kw_hits": best_kw_score,
        "best_kw_snippet": best_kw_snippet,
    })

# ── Save results ─────────────────────────────────────────────────────────────
out_path = os.path.join(BACKEND_DIR, "diagnosis_results.json")
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n\nDiagnosis complete. Results saved to: {out_path}")
