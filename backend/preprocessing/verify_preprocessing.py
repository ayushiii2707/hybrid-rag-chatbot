import json
import sys
from pathlib import Path

# Ensure parent directory is in path if executing in subfolder
sys.path.append(str(Path(__file__).parent))

from text_cleaner import TextCleaner
from spelling_corrector import SpellingCorrector
from entity_matcher import EntityMatcher


def main() -> None:
    print("--- Initializing NLP Preprocessing Components ---")
    cleaner = TextCleaner()
    corrector = SpellingCorrector()
    matcher = EntityMatcher()
    print("All components loaded successfully.")

    # 1. Simulate parsed document input from the Ingestion layer
    # We introduce a few typos, messy whitespace, and fuzzy vendor names
    mock_ingested_doc = {
        "doc_id": "70393f7539502291a2a2bb039d9f1b607885729a91e0ff5f046c8dc8b6b08e00",
        "source_file": "sample_invoice.pdf",
        "pages": [
            {
                "page_number": 1,
                "text": "   BILL TO:   Googl Inc  \n\n\n\nINVOICE  Number: INV-2026-992\nDate: 2026-05-20\nTotal Due: $1,250.00\n"
            },
            {
                "page_number": 2,
                "text": "Wenesday terms and conditons:\nPayment is due to IBM Corp within 30 days of the invoce date.\n"
            }
        ]
    }

    # 2. Run Preprocessing Pipeline
    print("\n--- Running Preprocessing Pipeline ---")
    enriched_pages = []

    for page in mock_ingested_doc["pages"]:
        raw_text = page["text"]
        page_num = page["page_number"]

        # Step 2a. Basic Cleaning
        clean_text_stage1 = cleaner.clean(raw_text)

        # Step 2b. Spelling Correction
        clean_text_stage2 = corrector.correct_text(clean_text_stage1)

        # Step 2c. Entity Extraction and Fuzzy Vendor Matching
        entities = matcher.extract_entities(clean_text_stage2)
        
        # Try to resolve vendor names from any ORG entity found on this page
        resolved_vendor = None
        for ent in entities:
            if ent["label"] == "ORG":
                match = matcher.match_vendor(ent["text"])
                if match:
                    resolved_vendor = match
                    break

        enriched_pages.append({
            "page_number": page_num,
            "raw_text": raw_text,
            "clean_text": clean_text_stage2,
            "entities": entities,
            "matched_vendor": resolved_vendor
        })

    # Assemble structured output
    preprocessed_doc = {
        "doc_id": mock_ingested_doc["doc_id"],
        "source_file": mock_ingested_doc["source_file"],
        "pages": enriched_pages
    }

    print("\nPreprocessed Enriched Document JSON:")
    print(json.dumps(preprocessed_doc, indent=2))

    # 3. Assertions and Validations
    print("\n--- Running Preprocessing Assertions ---")

    # Check structure
    assert "doc_id" in preprocessed_doc, "Missing 'doc_id'"
    assert "source_file" in preprocessed_doc, "Missing 'source_file'"
    assert len(preprocessed_doc["pages"]) == 2, "Expected 2 pages"

    # Verify Text Cleaner: spaces should be collapsed
    page1 = preprocessed_doc["pages"][0]
    assert "  " not in page1["clean_text"], "Extra spaces were not collapsed in TextCleaner."

    # Verify Spelling Corrector: "Wenesday" -> "Wednesday", "conditons" -> "conditions", "invoce" -> "invoice"
    page2 = preprocessed_doc["pages"][1]
    assert "Wednesday" in page2["clean_text"], f"Failed to correct 'Wenesday': {repr(page2['clean_text'])}"
    assert "conditions" in page2["clean_text"], f"Failed to correct 'conditons': {repr(page2['clean_text'])}"
    assert "invoice" in page2["clean_text"], f"Failed to correct 'invoce': {repr(page2['clean_text'])}"
    
    # Ensure code-like INV identifier INV-2026-992 was NOT corrupted by spellchecker
    assert "INV-2026-992" in page1["clean_text"], "Spellchecker corrupted invoice code identifier!"

    # Verify Entity Matcher & Fuzzy Vendor Matching: "Googl Inc" -> "Google", "IBM Corp" -> "IBM Corp"
    assert page1["matched_vendor"] == "Google", f"Failed fuzzy match for 'Googl Inc': {page1['matched_vendor']}"
    assert page2["matched_vendor"] == "IBM Corp", f"Failed match for 'IBM Corp': {page2['matched_vendor']}"

    # Verify entities contains ORG/MONEY
    p1_labels = [ent["label"] for ent in page1["entities"]]
    assert "MONEY" in p1_labels, "Should have extracted a MONEY entity ($1,250.00)"

    print("\n=======================================================")
    print("SUCCESS: NLP Preprocessing module verified successfully.")
    print("=======================================================")


if __name__ == "__main__":
    main()
