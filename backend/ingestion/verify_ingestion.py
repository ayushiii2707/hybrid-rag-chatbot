import json
import sys
from pathlib import Path
import fitz  # PyMuPDF

# Ensure parent directory is in path if executing in subfolder
sys.path.append(str(Path(__file__).parent))

from pdf_loader import PDFLoader
from pdf_parser import PDFParser


def create_mock_pdf(target_path: Path) -> None:
    """
    Creates a simple mock PDF with two pages of text using PyMuPDF.

    Args:
        target_path (Path): Destination file path for the mock PDF.
    """
    print(f"[TEST SETUP] Generating mock PDF at: {target_path}")
    doc = fitz.open()

    # Create Page 1
    page1 = doc.new_page()
    page1.insert_text(
        (50, 50),
        "VENDOR INVOICE\nInvoice Number: INV-2026-001\nDate: 2026-05-20\nTotal Amount Due: $1,250.00",
    )

    # Create Page 2
    page2 = doc.new_page()
    page2.insert_text(
        (50, 100),
        "Terms and Conditions\nPayment is due within 30 days of invoice date.\nThank you for your business!",
    )

    # Save and finalize the document
    doc.save(target_path)
    doc.close()
    print("[TEST SETUP] Mock PDF generated successfully.")


def main() -> None:
    # Resolve backend/datasets/raw_pdfs directory
    base_dir = Path(__file__).resolve().parents[1]
    raw_dir = base_dir / "datasets" / "raw_pdfs"
    raw_dir.mkdir(parents=True, exist_ok=True)

    mock_pdf_path = raw_dir / "sample_invoice.pdf"
    create_mock_pdf(mock_pdf_path)

    # 1. Validate PDFLoader
    print("\n--- Testing PDFLoader ---")
    loader = PDFLoader(default_directory=raw_dir)
    pdf_paths = loader.load_from_directory()
    print(f"Discovered PDFs: {pdf_paths}")
    assert len(pdf_paths) >= 1, "Should discover at least 1 PDF in the directory."
    assert mock_pdf_path in pdf_paths, "Should find our generated mock PDF."

    specific_paths = loader.load_specific_files([mock_pdf_path])
    assert specific_paths == [mock_pdf_path], "Should resolve the exact list of specific files."
    print("PDFLoader: Discovered and loaded paths verified successfully.")

    # 2. Validate PDFParser
    print("\n--- Testing PDFParser ---")
    parser = PDFParser()
    parsed_doc = parser.parse_pdf(mock_pdf_path)

    print("\nStructured Parsed Document Output:")
    print(json.dumps(parsed_doc, indent=2))

    # Assert contract structure
    assert "doc_id" in parsed_doc, "Parsed document contract is missing 'doc_id'."
    assert parsed_doc["source_file"] == "sample_invoice.pdf", "Parsed document 'source_file' mismatch."
    assert len(parsed_doc["pages"]) == 2, f"Expected 2 pages, got {len(parsed_doc['pages'])}."
    
    # Assert page content & indices
    p1 = parsed_doc["pages"][0]
    p2 = parsed_doc["pages"][1]
    assert p1["page_number"] == 1, "First page index should be 1 (1-indexed)."
    assert "VENDOR INVOICE" in p1["text"], "Expected text not found on page 1."
    assert p2["page_number"] == 2, "Second page index should be 2 (1-indexed)."
    assert "Terms and Conditions" in p2["text"], "Expected text not found on page 2."

    print("\nPDFParser: Output contract and structural assertions passed.")
    print("\n=======================================================")
    print("SUCCESS: Ingestion module verified successfully.")
    print("=======================================================")


if __name__ == "__main__":
    main()
