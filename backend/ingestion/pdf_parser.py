import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Union
import fitz  # PyMuPDF

# Configure basic logging for the parser module
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class PDFParserException(Exception):
    """
    Custom exception raised during PDF extraction failure (e.g. encrypted or corrupted file).
    """
    pass


class PDFParser:
    """
    A production-grade PDF parser that extracts text page-by-page using PyMuPDF (fitz)
    and formats the parsed text into a structured JSON-compatible output.
    """

    @staticmethod
    def calculate_doc_id(file_path: Path) -> str:
        """
        Calculates a unique, deterministic SHA-256 document ID based on the file content.

        Args:
            file_path (Path): Path to the target PDF file.

        Returns:
            str: Hex digest representing the unique SHA-256 document ID.
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read file in 4096-byte chunks to support large files efficiently
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def parse_pdf(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Parses the PDF document, extracting raw text and formatting it page-by-page.

        Args:
            file_path (Union[str, Path]): Path to the target PDF file.

        Returns:
            Dict[str, Any]: Structured dictionary matching the required contract:
                {
                    "doc_id": str,          # SHA-256 checksum of contents
                    "source_file": str,     # Basename of the file (e.g. "invoice.pdf")
                    "pages": [
                        {
                            "page_number": int, # 1-indexed page number
                            "text": str         # Extracted raw text
                        }
                    ]
                }

        Raises:
            FileNotFoundError: If the target PDF file does not exist.
            ValueError: If the input path is not a file.
            PDFParserException: If the file is password-protected or structurally corrupted.
        """
        path = Path(file_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found at: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a valid file: {path}")

        doc_id = self.calculate_doc_id(path)
        source_file = path.name
        pages_data: List[Dict[str, Any]] = []

        try:
            # Open PDF with PyMuPDF
            with fitz.open(path) as doc:
                if doc.is_encrypted:
                    raise PDFParserException(
                        f"Cannot parse encrypted or password-protected PDF file: {path}"
                    )

                if len(doc) == 0:
                    logger.warning(f"Parsed PDF document contains 0 pages: {path}")

                for page_idx, page in enumerate(doc):
                    page_num = page_idx + 1
                    try:
                        # Extract plain text from page
                        text = page.get_text()
                        pages_data.append({
                            "page_number": page_num,
                            "text": text
                        })
                    except Exception as page_err:
                        logger.error(
                            f"Error extracting text from page {page_num} of {path.name}: {page_err}"
                        )
                        # Gracefully fall back to empty string to ensure processing continues
                        pages_data.append({
                            "page_number": page_num,
                            "text": ""
                        })

        except fitz.FileDataError as fde:
            raise PDFParserException(f"Corrupted or invalid PDF structure: {path}") from fde
        except Exception as e:
            if not isinstance(e, PDFParserException):
                raise PDFParserException(f"Unexpected error during PDF parsing: {e}") from e
            raise

        logger.info(
            f"Successfully parsed document: {source_file} (doc_id: {doc_id}, pages: {len(pages_data)})"
        )
        return {
            "doc_id": doc_id,
            "source_file": source_file,
            "pages": pages_data
        }


# Example usage block
if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_parser.py <path_to_pdf>")
    else:
        parser = PDFParser()
        try:
            result = parser.parse_pdf(sys.argv[1])
            print(json.dumps(result, indent=2))
        except Exception as error:
            print(f"Error parsing PDF: {error}")
