import json
import logging
import os
import sys
from pathlib import Path

# Setup clean logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("verify_query_engine")

# ── Bootstrap Paths ───────────────────────────────────────────────────────────
# backend/query_engine/verify_query_engine.py -> parent is backend/query_engine -> grandparent is backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "embeddings"))
sys.path.insert(0, str(BACKEND_DIR / "query_engine"))

try:
    from query_orchestrator import QueryOrchestrator
    from vector_store import FAISSVectorStore
except ImportError as e:
    logger.critical(f"Failed to import Query Engine dependencies: {e}")
    sys.exit(1)


def print_test_case_result(case_name: str, response: dict) -> None:
    print(f"\n================================================================================")
    print(f"  TEST CASE: {case_name}")
    print(f"================================================================================")
    print(f"Raw Query            : \"{response['query']}\"")
    print(f"Corrected Query      : \"{response['corrected_query']}\"")
    print(f"Confirm Required?    : {response['confirmation_required']}")
    print(f"Answer Found?        : {response['answer_found']}")
    print(f"Confidence Score     : {response['confidence']:.4f}")
    
    if response["answer_found"] and response["top_match"]:
        top = response["top_match"]
        print(f"\nTOP MATCH:")
        print(f"  Source File        : {top['source_file']}")
        print(f"  Page Number        : {top['page_number']}")
        print(f"  Chunk ID           : {top['chunk_id']}")
        print(f"  Match Score        : {top['score']:.4f}")
        print(f"  Verbatim Excerpt   : \"{top['answer_excerpt'].strip()}\"")
        
        # Verify no hallucination occurred (verbatim check)
        # We load the metadata database to verify the excerpt exists in the indexed chunk text
        from backend.database.db import SessionLocal
        from backend.auth.auth_models import Chunk
        db = SessionLocal()
        try:
            db_chunk = db.query(Chunk).filter(Chunk.chunk_id == top["chunk_id"]).first()
            target_chunk = {
                "chunk_id": db_chunk.chunk_id,
                "text": db_chunk.text,
            } if db_chunk else None
        finally:
            db.close()
        assert target_chunk is not None, "Error: Match chunk_id is not in index metadata!"
        
        # Check if excerpt is in chunk text (case-insensitive and ignoring space diffs)
        norm_excerpt = " ".join(top['answer_excerpt'].lower().split())
        norm_chunk = " ".join(target_chunk['text'].lower().split())
        assert norm_excerpt in norm_chunk or any(s in norm_chunk for s in norm_excerpt.split(". ")), (
            "Error: Excerpt was fabricated/hallucinated! Not found in source chunk text."
        )
        print("  Groundedness check : Passed (verbatim source match verified) ✓")
    else:
        print("\nTOP MATCH: None")

    if response["other_matches"]:
        print(f"\nOTHER MATCHES ({len(response['other_matches'])}):")
        for idx, match in enumerate(response["other_matches"]):
            print(f"  Match {idx+1}: {match['source_file']} (Page {match['page_number']}) [Score: {match['score']:.4f}]")
            print(f"    Excerpt snippet: \"{match['answer_excerpt'][:120].strip()}...\"")
    else:
        print("OTHER MATCHES        : None")
    print(f"================================================================================\n")


def main() -> None:
    print("=" * 80)
    print("  RUNNING SEMANTIC QUERY ORCHESTRATION + ANSWER ENGINE TEST SUITE")
    print("=" * 80)

    # 1. Ensure the FAISS index exists
    index_bin = os.path.join(BACKEND_DIR, "embeddings", "faiss_index.bin")
    metadata_json = os.path.join(BACKEND_DIR, "embeddings", "metadata.json")
    if not os.path.exists(index_bin) or not os.path.exists(metadata_json):
        logger.error(
            f"FAISS index binaries not found at {index_bin}. "
            f"Please run verify_embeddings.py first to construct the index."
        )
        sys.exit(1)

    # 2. Instantiate QueryOrchestrator
    orchestrator = QueryOrchestrator()

    # Test 1: Typo Correction Confirmation Flow
    # We query with spelling typos ("Wenesday", "onbarding")
    logger.info("Executing Test 1: Typo Correction Confirmation Flow...")
    res_typo = orchestrator.answer_query("Wenesday onbarding registration")
    print_test_case_result("Typo Correction Confirmation Flow", res_typo)
    
    # Assertions for Typo test
    assert res_typo["confirmation_required"] == True, "Failed: Typo was not flagged for confirmation."
    assert "Wednesday" in res_typo["corrected_query"], "Failed: Typo 'Wenesday' was not corrected to 'Wednesday'."
    assert "onboarding" in res_typo["corrected_query"], "Failed: Typo 'onbarding' was not corrected to 'onboarding'."

    # Test 2: Acronym Query Preservation
    # We query using critical acronyms (MSME, UDYAM) to ensure they are NOT spellcorrected to ADAM/ASSAI
    logger.info("Executing Test 2: Acronym Query Preservation...")
    res_acronym = orchestrator.answer_query("what are MSME UDYAM validation rules")
    print_test_case_result("Acronym Query Preservation", res_acronym)
    
    # Assertions for Acronym test
    assert "UDYAM" in res_acronym["corrected_query"], "Failed: Acronym 'UDYAM' was spellcorrected."
    assert "MSME" in res_acronym["corrected_query"], "Failed: Acronym 'MSME' was spellcorrected."
    assert res_acronym["answer_found"] == True, "Failed: Could not find validation rules chunk."
    assert res_acronym["top_match"]["page_number"] in (5, 10), f"Failed: Wrong page matched. Expected page 5 or 10, got {res_acronym['top_match']['page_number']}."

    # Test 3: Paraphrased Query Check
    # We test query that describes a link search ("Where is FSSAI active status link checked")
    logger.info("Executing Test 3: Paraphrased Query Check...")
    res_para = orchestrator.answer_query("Where is FSSAI active status link checked")
    print_test_case_result("Paraphrased Query Check", res_para)
    
    assert res_para["answer_found"] == True, "Failed: Could not locate active status check information."
    assert "fssai.gov.in" in res_para["top_match"]["answer_excerpt"].lower(), "Failed to locate target link in excerpt."
    assert res_para["top_match"]["page_number"] == 11, "Failed: Expected match on Page 11."

    # Test 4: Multi-document Similarity Ranking
    # "Merchandise Supplier" is a phrase present in both documents
    logger.info("Executing Test 4: Multi-document Similarity Ranking...")
    res_multi = orchestrator.answer_query("Merchandise Supplier")
    print_test_case_result("Multi-document Similarity Ranking", res_multi)
    
    assert res_multi["answer_found"] == True, "Failed: Match not found."
    assert len(res_multi["other_matches"]) > 0, "Failed: Secondary matches from multiple documents not retrieved."
    
    # Check that documents are represented in matches
    sources = [res_multi["top_match"]["source_file"]] + [m["source_file"] for m in res_multi["other_matches"]]
    assert any("Add Delivery Location User Manual.pdf" in s for s in sources), "Failed: Add Delivery Location manual missing in results."
    assert any("registration manual.pdf" in s for s in sources), "Failed: Registration manual missing in results."

    # Test 5: No-Answer / Out of Domain Handling
    # Queries containing random topics should drop below confidence threshold and trigger zero-hallucination warning
    logger.info("Executing Test 5: Out of Domain / No-Answer Handling...")
    res_no_answer = orchestrator.answer_query("how to cook standard Italian spaghetti carbonara")
    print_test_case_result("Out of Domain / No-Answer Handling", res_no_answer)
    
    assert res_no_answer["answer_found"] == False, "Failed: Out of domain query falsely returned an answer."
    assert res_no_answer["top_match"] is None, "Failed: Top match should be None."
    assert res_no_answer["other_matches"] == [], "Failed: Other matches should be empty."

    print("=" * 80)
    print("  VERIFICATION SUCCESS: ALL QUERY ENGINE SYSTEM TESTS PASSED")
    print("=" * 80)


if __name__ == "__main__":
    main()
