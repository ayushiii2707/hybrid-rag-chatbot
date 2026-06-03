import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Boilerplate patterns commonly found in headers, footers, page numbering, and navigation
BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*page\s*\d+(?:\s*of\s*\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$", re.IGNORECASE),  # Line containing only numbers (e.g. page number or table index)
    re.compile(r"all\s+rights\s+reserved", re.IGNORECASE),
    re.compile(r"confidential", re.IGNORECASE),
    re.compile(r"copyright\s*(?:\(c\))?\s*\d{4}", re.IGNORECASE),
    re.compile(r"^\s*click\s+here\s*$", re.IGNORECASE),
    re.compile(r"^\s*table\s+of\s+contents\s*$", re.IGNORECASE)
]

class ChunkQualityAnalyzer:
    """
    Analyzes text chunks for structural and quality issues (abrupt endings, 
    low letter/number ratios, OCR noise, and header/footer boilerplate density).
    Produces a quality score between 0.0 (noise) and 1.0 (high quality).
    """

    def __init__(self) -> None:
        pass

    def analyze(self, text: str) -> float:
        """
        Analyzes the quality of a text chunk.

        Args:
            text (str): Verbatim chunk text content.

        Returns:
            float: Quality score in the range [0.0, 1.0].
        """
        if not text or not text.strip():
            return 0.0

        score = 1.0
        stripped = text.strip()

        # 1. Abrupt ending check
        # A high-quality chunk should end with standard punctuation (. ? !) or closed quote/bracket.
        # If it ends mid-sentence (e.g. alphanumeric character, comma, or preposition), penalize it.
        ends_with_punctuation = bool(re.search(r"[.!?\"')\]]$", stripped))
        if not ends_with_punctuation:
            score -= 0.15
            logger.debug("Quality Penalty: Abrupt ending (does not end with standard sentence punctuation).")

        # 2. Low information / High special char ratio checks
        total_len = len(stripped)
        letter_count = sum(1 for c in stripped if c.isalpha())
        digit_count = sum(1 for c in stripped if c.isdigit())
        special_count = sum(1 for c in stripped if not c.isalnum() and not c.isspace())

        letter_ratio = letter_count / total_len if total_len > 0 else 0.0
        special_ratio = special_count / total_len if total_len > 0 else 0.0

        # Penalty for extremely low letter ratio (e.g., tables of numbers, code snippets, or OCR noise)
        if letter_ratio < 0.50:
            # Smooth penalty: scales up as letter ratio drops below 50%
            penalty = (0.50 - letter_ratio) * 0.50
            score -= penalty
            logger.debug(f"Quality Penalty: Low letter ratio {letter_ratio:.2f}. Penalty: {penalty:.4f}")

        # Penalty for high density of special characters (potential OCR/layout noise)
        if special_ratio > 0.15:
            # Smooth penalty for special character ratio
            penalty = (special_ratio - 0.15) * 0.50
            score -= penalty
            logger.debug(f"Quality Penalty: High special char ratio {special_ratio:.2f}. Penalty: {penalty:.4f}")

        # 3. Header/Footer Boilerplate check
        # Split chunk into lines and see what percentage of lines match boilerplate patterns or look like header metadata.
        lines = [line.strip() for line in stripped.split("\n") if line.strip()]
        boilerplate_lines_count = 0

        for line in lines:
            # A line is boilerplate if it matches any pattern
            is_boilerplate = False
            for pattern in BOILERPLATE_PATTERNS:
                if pattern.match(line) or pattern.search(line):
                    is_boilerplate = True
                    break
            
            # Short UPPERCASE lines of less than 30 chars are often repetitive headers/titles
            if not is_boilerplate and len(line) < 30 and line.isupper() and line.isalpha():
                is_boilerplate = True

            if is_boilerplate:
                boilerplate_lines_count += 1

        if lines:
            boilerplate_ratio = boilerplate_lines_count / len(lines)
            if boilerplate_ratio > 0.20:
                # Deduct based on how much boilerplate is present
                penalty = min(0.25, boilerplate_ratio * 0.50)
                score -= penalty
                logger.debug(f"Quality Penalty: Boilerplate lines ratio {boilerplate_ratio:.2f}. Penalty: {penalty:.4f}")

        # Ensure final score is strictly bounded [0.0, 1.0]
        final_score = max(0.0, min(1.0, score))
        logger.debug(f"Chunk Quality Analysis: text_len={total_len}, letter_ratio={letter_ratio:.2f}, "
                     f"special_ratio={special_ratio:.2f}, score={final_score:.4f}")
        return final_score

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    analyzer = ChunkQualityAnalyzer()
    
    # High quality sample
    t1 = "This is a clean sentence explaining the onboarding process for new vendors. It has proper endings."
    # Low quality samples
    t2 = "This is an unfinished sentence without punctuation"
    t3 = "Page 10\nCONFIDENTIAL\n12345\n99.9% / 88.8% -- *#$@!!"
    
    print("t1 score:", analyzer.analyze(t1))
    print("t2 score:", analyzer.analyze(t2))
    print("t3 score:", analyzer.analyze(t3))
