import logging
import os
import sys
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ── Bootstrap Paths ───────────────────────────────────────────────────────────
# backend/query_engine/query_preprocessor.py -> parent is backend/query_engine -> grandparent is backend/
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "preprocessing"))

try:
    from text_cleaner import TextCleaner
    from spelling_corrector import SpellingCorrector
except ImportError as e:
    logger.critical(f"Failed to import preprocessing modules from path: {e}")
    raise RuntimeError("Import failed in QueryPreprocessor") from e


class QueryPreprocessor:
    """
    Query Preprocessor that leverages the same cleaning and robust spelling
    correction components used during document indexing. 
    It maintains compatibility for acronyms, identifiers, and determines whether
    a spelling correction needs confirmation.
    """

    def __init__(self, config_path: str = None) -> None:
        """
        Initializes the QueryPreprocessor and loads cleaning and correction components.
        """
        logger.info("Initializing QueryPreprocessor...")
        # SpellingCorrector will load its config relative to its directory
        self.cleaner = TextCleaner()
        self.corrector = SpellingCorrector()
        
        # Register ignored words in SymSpell frequency dictionary
        # to allow correcting to these terms (e.g. "onbarding" -> "onboarding")
        if hasattr(self.corrector, "ignored_words") and hasattr(self.corrector, "sym_spell"):
            for word in self.corrector.ignored_words:
                cleaned_word = word.strip().lower()
                if cleaned_word.isalpha():
                    try:
                        self.corrector.sym_spell.create_dictionary_entry(cleaned_word, 10000000)
                        logger.info(f"Registered custom vocabulary entry: '{cleaned_word}'")
                    except Exception as e:
                        logger.warning(f"Could not register custom vocabulary '{cleaned_word}': {e}")
                        
        logger.info("QueryPreprocessor components initialized successfully.")

    def _normalize_string(self, text: str) -> str:
        """Helper to normalize text case-insensitively with single spacing for diff checks."""
        if not text:
            return ""
        return " ".join(text.lower().split())

    def preprocess_query(self, query: str) -> Dict[str, Any]:
        """
        Cleans and corrects typos in a query string. Sets flags if significant changes occur.

        Args:
            query (str): The raw incoming query string.

        Returns:
            Dict[str, Any]: Dict containing the preprocessed query information:
                {
                    "original_query": str,
                    "cleaned_query": str,
                    "corrected_query": str,
                    "confirmation_required": bool
                }
        """
        if not query:
            return {
                "original_query": "",
                "cleaned_query": "",
                "corrected_query": "",
                "confirmation_required": False
            }

        # 1. Strip markup and collapse spacing
        cleaned_query = self.cleaner.clean(query)

        # 2. Correct spelling using robust SymSpell wrapper
        corrected_query = self.corrector.correct_text(cleaned_query)

        # 3. Determine if confirmation is required by comparing normalized versions
        norm_cleaned = self._normalize_string(cleaned_query)
        norm_corrected = self._normalize_string(corrected_query)
        
        confirmation_required = norm_cleaned != norm_corrected

        logger.info(
            f"Query preprocessed: original='{query}', corrected='{corrected_query}', "
            f"confirmation_required={confirmation_required}"
        )

        return {
            "original_query": query,
            "cleaned_query": cleaned_query,
            "corrected_query": corrected_query,
            "confirmation_required": confirmation_required
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    preprocessor = QueryPreprocessor()
    res = preprocessor.preprocess_query("FSSAI licnce onbarding rules")
    print(res)
