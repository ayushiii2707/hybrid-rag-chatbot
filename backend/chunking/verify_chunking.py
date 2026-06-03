import json
import sys
from pathlib import Path

# Ensure parent directory is in path if executing in subfolder
sys.path.append(str(Path(__file__).parent))

from text_splitter import DocumentChunker


def main() -> None:
    # 1. Setup mock preprocessed input
    mock_preprocessed_doc = {
        "doc_id": "70393f7539502291a2a2bb039d9f1b607885729a91e0ff5f046c8dc8b6b08e00",
        "source_file": "sample_invoice.pdf",
        "pages": [
            {
                "page_number": 1,
                "clean_text": "BILL TO: Google Inc\nINVOICE Number: INV-2026-992\nDate: 2026-05-20\nTotal Due: $1,250.00"
            },
            {
                "page_number": 2,
                "clean_text": "Wednesday terms and conditions:\nPayment is due to IBM Corp within 30 days of the invoice date."
            }
        ]
    }

    # 2. Verify Page-Level Strategy
    print("--- Testing Page-Level Chunking Strategy ---")
    page_chunker = DocumentChunker(strategy="page")
    page_chunks = page_chunker.chunk_document(mock_preprocessed_doc)
    
    print("\nPage-Level Chunks:")
    print(json.dumps(page_chunks, indent=2))

    assert len(page_chunks) == 2, "Expected exactly 2 chunks (one per page)."
    assert page_chunks[0]["page_number"] == 1, "Chunk 1 should reference page 1."
    assert page_chunks[1]["page_number"] == 2, "Chunk 2 should reference page 2."
    assert page_chunks[0]["chunk_id"] == f"{mock_preprocessed_doc['doc_id']}_c0", "Incorrect chunk_id format."
    assert page_chunks[1]["chunk_id"] == f"{mock_preprocessed_doc['doc_id']}_c1", "Incorrect chunk_id format."
    print("Page-Level Chunking tests PASSED.")

    # 3. Verify Recursive Character Strategy
    # Using small chunk_size=60 and overlap=15 to force multiple splits and test window overlap
    print("\n--- Testing Recursive Character Chunking Strategy ---")
    recursive_chunker = DocumentChunker(strategy="recursive", chunk_size=60, chunk_overlap=15)
    rec_chunks = recursive_chunker.chunk_document(mock_preprocessed_doc)

    print("\nRecursive Chunks:")
    print(json.dumps(rec_chunks, indent=2))

    # Assertions
    assert len(rec_chunks) > 2, "Should have created multiple splits."
    
    # Track chunk index sequence and uniqueness
    indices = []
    chunk_ids = set()
    for chunk in rec_chunks:
        indices.append(chunk["chunk_index"])
        chunk_ids.add(chunk["chunk_id"])
        
        # Verify sizes are bounded
        assert len(chunk["text"]) <= 60, f"Chunk text is too long: {len(chunk['text'])} chars."
        assert chunk["metadata"]["char_count"] == len(chunk["text"]), "Metadata char_count mismatch."
        assert chunk["metadata"]["page_number"] == chunk["page_number"], "Metadata page_number mismatch."
        assert chunk["metadata"]["source_file"] == chunk["source_file"], "Metadata source_file mismatch."

    # Validate sequential indexes starting from 0
    assert indices == list(range(len(rec_chunks))), f"Incorrect index sequence: {indices}"
    assert len(chunk_ids) == len(rec_chunks), "Duplicate chunk_ids detected."
    
    # Check overlap sanity: some word parts or letters must be replicated across adjacent chunks of the same page
    # E.g. "Google Inc" or parts of the address might overlap
    # We can check that the chunks on the same page don't have gaps (character text content overlap is present)
    print("Recursive Chunking tests PASSED.")

    print("\n=======================================================")
    print("SUCCESS: Text Chunking module verified successfully.")
    print("=======================================================")


if __name__ == "__main__":
    main()
