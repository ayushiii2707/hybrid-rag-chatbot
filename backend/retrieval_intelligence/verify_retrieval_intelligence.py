import json
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("verify_retrieval_intelligence")

# ── Bootstrap Paths ───────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "embeddings"))
sys.path.insert(0, str(BACKEND_DIR / "query_engine"))
sys.path.insert(0, str(BACKEND_DIR / "retrieval_intelligence"))

try:
    from query_orchestrator import QueryOrchestrator
    from hybrid_retriever import HybridRetriever
except ImportError as e:
    logger.critical(f"Failed to import Retrieval Intelligence verification dependencies: {e}")
    sys.exit(1)


def print_test_case_header(case_name: str) -> None:
    print(f"\n" + "=" * 80)
    print(f"  TEST CASE: {case_name}")
    print(f"=" * 80)


def run_tests() -> None:
    logger.info("Initializing QueryOrchestrator with Retrieval Intelligence Layer...")
    orchestrator = QueryOrchestrator()
    logger.info("QueryOrchestrator initialized successfully.")

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 1: Reranking Quality and Acronym Preservation
    # ──────────────────────────────────────────────────────────────────────────
    print_test_case_header("Reranking Quality & Acronym Preservation")
    q1 = "what are MSME UDYAM validation rules"
    res1 = orchestrator.answer_query(q1)
    
    print(f"Query                : \"{q1}\"")
    print(f"Corrected Query      : \"{res1['corrected_query']}\"")
    print(f"Answer Found?        : {res1['answer_found']}")
    print(f"Confidence Score     : {res1['confidence']:.4f}")
    
    # Assertions
    assert "UDYAM" in res1["corrected_query"], "Fail: Acronym 'UDYAM' was spellcorrected incorrectly!"
    assert "MSME" in res1["corrected_query"], "Fail: Acronym 'MSME' was spellcorrected incorrectly!"
    assert res1["answer_found"] == True, "Fail: Did not find validation rules chunk!"
    assert res1["top_match"]["page_number"] == 10, "Fail: Expected page number 10!"
    
    # Let's inspect the breakdown details for the top match
    # Since we returned candidate through HybridRetriever, let's fetch candidate pool to inspect breakdowns
    retriever = orchestrator.retrieval_engine
    candidates = retriever.retrieve(res1["corrected_query"], top_k=3)
    
    print(f"Top Match Source     : {res1['top_match']['source_file']}")
    print(f"Top Match Page       : {res1['top_match']['page_number']}")
    print(f"Top Match Chunk ID   : {res1['top_match']['chunk_id']}")
    print(f"Top Match Score      : {res1['top_match']['score']:.4f}")
    print(f"Top Match Excerpt    : \"{res1['top_match']['answer_excerpt'].strip()}\"")
    
    # ──────────────────────────────────────────────────────────────────────────
    # TEST 2: Confidence Calibration & Breakdown Verification
    # ──────────────────────────────────────────────────────────────────────────
    print_test_case_header("Confidence Calibration Breakdown verification")
    assert len(candidates) > 0, "Fail: No candidates returned from retriever!"
    top_cand = candidates[0]
    assert "breakdown" in top_cand, "Fail: Reranked candidate does not contain confidence breakdown details!"
    
    breakdown = top_cand["breakdown"]
    print("Top Match Confidence Score Breakdown:")
    for key, val in breakdown.items():
        print(f"  - {key:<22}: {val}")
        
    assert "semantic" in breakdown, "Fail: Semantic score missing from breakdown!"
    assert "keyword" in breakdown, "Fail: Keyword score missing from breakdown!"
    assert "entity" in breakdown, "Fail: Entity score missing from breakdown!"
    assert "metadata" in breakdown, "Fail: Metadata score missing from breakdown!"
    assert "quality" in breakdown, "Fail: Quality score missing from breakdown!"
    print("Confidence calibration breakdown verified ✓")

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 3: Interactive Refinement / Fallback Logic
    # ──────────────────────────────────────────────────────────────────────────
    print_test_case_header("Interactive Refinement / Next-Best Fallback Logic")
    # Fetch first answer
    q3 = "UDYAM registration validation rules"
    res_first = orchestrator.answer_query(q3)
    first_chunk_id = res_first["top_match"]["chunk_id"]
    print(f"First Top Match ID   : {first_chunk_id} (Score: {res_first['confidence']:.4f})")
    
    # Simulate user rejecting the first answer: answer_satisfied = False
    res_second = orchestrator.answer_query(q3, answer_satisfied=False, last_chunk_id=first_chunk_id)
    second_chunk_id = res_second["top_match"]["chunk_id"]
    print(f"Second Top Match ID  : {second_chunk_id} (Score: {res_second['confidence']:.4f})")
    
    assert second_chunk_id != first_chunk_id, "Fail: Interactive refinement served the same chunk ID!"
    assert res_second["confidence"] <= res_first["confidence"], "Fail: Second best match has higher score than top match!"
    print("Interactive refinement check passed ✓")

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 4: Out-of-Domain Query & Clarification Recommendations
    # ──────────────────────────────────────────────────────────────────────────
    print_test_case_header("Out-of-Domain Query & Clarification recommendations")
    q4 = "how to cook standard Italian spaghetti carbonara"
    res_ood = orchestrator.answer_query(q4)
    
    print(f"Query                : \"{q4}\"")
    print(f"Answer Found?        : {res_ood['answer_found']}")
    print(f"Confidence Score     : {res_ood['confidence']:.4f}")
    print(f"Clarification Req?   : {res_ood['clarification_required']}")
    print(f"Clarification Prompts: {res_ood['clarification_prompts']}")
    
    assert res_ood["answer_found"] == False, "Fail: Out of domain query falsely returned an answer!"
    assert res_ood["clarification_required"] == True, "Fail: Clarification flag not set for low-confidence query!"
    assert len(res_ood["clarification_prompts"]) > 0, "Fail: No clarification recommendations generated!"
    print("Out-of-domain and query clarification recommendations check passed ✓")

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 5: FSSAI Active Link Retrieval verification
    # ──────────────────────────────────────────────────────────────────────────
    print_test_case_header("FSSAI Active Link Retrieval Verification")
    q5 = "Where is FSSAI active status checked"
    res5 = orchestrator.answer_query(q5)
    
    print(f"Query                : \"{q5}\"")
    print(f"Corrected Query      : \"{res5['corrected_query']}\"")
    print(f"Answer Found?        : {res5['answer_found']}")
    print(f"Confidence Score     : {res5['confidence']:.4f}")
    print(f"Top Match Page       : {res5['top_match']['page_number']}")
    print(f"Top Match Excerpt    : \"{res5['top_match']['answer_excerpt'].strip()}\"")
    
    assert res5["answer_found"] == True, "Fail: Did not find active status check!"
    assert res5["top_match"]["page_number"] == 11, "Fail: Expected page number 11 for active link!"
    assert "fssai.gov.in" in res5["top_match"]["answer_excerpt"].lower(), "Fail: Target link 'fssai.gov.in' not in excerpt!"
    print("FSSAI Active Link retrieval verified ✓")

    print("\n" + "=" * 80)
    print("  VERIFICATION SUCCESS: ALL RETRIEVAL INTELLIGENCE LAYER TESTS PASSED!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
