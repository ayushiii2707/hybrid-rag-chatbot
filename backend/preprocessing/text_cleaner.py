import logging
import re

logger = logging.getLogger(__name__)


class TextCleaner:
    """
    A production-grade text cleaner for standardizing raw PDF text outputs.
    Preserves document structure necessary for downstream extractive QA (e.g. spaces/newlines),
    while normalizing multiple whitespaces, non-printable characters, and tabs.
    """

    def __init__(self, lowercase: bool = False, remove_extra_whitespace: bool = True) -> None:
        """
        Initializes the TextCleaner.

        Args:
            lowercase (bool): If True, converts all cleaned text to lowercase.
            remove_extra_whitespace (bool): If True, collapses multiple spaces/newlines.
        """
        self.lowercase = lowercase
        self.remove_extra_whitespace = remove_extra_whitespace

    def clean(self, text: str) -> str:
        """
        Cleans and normalizes the input text string.

        Args:
            text (str): Raw text extracted from a PDF page.

        Returns:
            str: Cleaned and normalized text.
        """
        if not text:
            return ""

        # 1. Remove non-printable/control characters (preserving standard newlines and tabs)
        # Keep character categories: printable chars, space, tabs, newlines
        cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")

        # 2. Normalize Windows-style (\r\n) line endings to Unix-style (\n)
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Clean up tabs by converting them to single spaces
        cleaned = cleaned.replace("\t", " ")

        # 4. Collapse extra whitespaces if enabled
        if self.remove_extra_whitespace:
            # Collapse multiple spaces on the same line to a single space
            cleaned = re.sub(r"[ \t]+", " ", cleaned)
            # Collapse three or more consecutive newlines into a maximum of two (preserves paragraph splits)
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
            # Strip trailing/leading spaces on each individual line
            cleaned = "\n".join(line.strip() for line in cleaned.split("\n"))

        # 5. Convert to lowercase if enabled
        if self.lowercase:
            cleaned = cleaned.lower()

        # Final strip
        return cleaned.strip()


# Example usage block
if __name__ == "__main__":
    cleaner = TextCleaner()
    raw = "  VENDOR   INVOICE \n\n\n\nINV-2026-001\t\t$1,250.00\r\n\r\n"
    print(f"Raw: {repr(raw)}")
    print(f"Cleaned: {repr(cleaner.clean(raw))}")
