import logging
import os
import re
from typing import Set
from symspellpy import SymSpell, Verbosity

logger = logging.getLogger(__name__)


class SpellingCorrector:
    """
    A production-grade spelling corrector wrapping SymSpell.
    Configured to correct common standard English spelling and OCR errors,
    while carefully ignoring alphanumeric codes, invoice IDs, price amounts,
    and acronyms to prevent data loss.
    """

    def __init__(
        self,
        max_edit_distance: int = 2,
        prefix_length: int = 7,
        ignored_words: Set[str] = None,
    ) -> None:
        """
        Initializes the SpellingCorrector and loads the default SymSpell English dictionary.

        Args:
            max_edit_distance (int): Maximum edit distance for suggestions (default 2).
            prefix_length (int): Prefix length for SymSpell index (default 7).
            ignored_words (Set[str]): Specific words that should never be corrected.
        """
        self.sym_spell = SymSpell(
            max_dictionary_edit_distance=max_edit_distance, prefix_length=prefix_length
        )
        
        self.ignored_words = set()
        if ignored_words:
            self.ignored_words.update(w.lower() for w in ignored_words)
        else:
            try:
                import json
                config_path = os.path.join(os.path.dirname(__file__), "config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                    ignored = config_data.get("spelling_corrector", {}).get("ignored_words", [])
                    self.ignored_words.update(w.lower() for w in ignored)
                    logger.info(f"Loaded {len(ignored)} ignored words from config.")
            except Exception as e:
                logger.warning(f"Could not load ignored words from config.json: {e}")

        # Locate the default frequency dictionary inside symspellpy package cleanly without warnings
        try:
            import symspellpy
            sym_path = os.path.dirname(symspellpy.__file__)
            dict_path = os.path.join(sym_path, "frequency_dictionary_en_82_765.txt")

            if not os.path.exists(dict_path):
                raise FileNotFoundError(f"SymSpell dictionary file not found at: {dict_path}")

            # Load the dictionary: column 0 is term, column 1 is frequency count
            self.sym_spell.load_dictionary(dict_path, term_index=0, count_index=1)
            logger.info("SymSpell English dictionary loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load SymSpell dictionary: {e}")
            raise RuntimeError("SymSpell initialization failed.") from e

    def _should_correct(self, token: str) -> bool:
        """
        Determines whether a given token is a standard word that should be corrected.

        Args:
            token (str): The string token to evaluate.

        Returns:
            bool: True if the token is eligible for spell correction, False otherwise.
        """
        # Skip if empty or in our explicit ignored list (case-insensitive)
        if not token or token.lower() in self.ignored_words:
            return False

        # Skip words containing numbers, symbols, or currency characters (e.g. $100, INV-2026, 12/05)
        if any(char.isdigit() for char in token):
            return False

        # Skip very short tokens (length < 3) since they are likely acronyms, codes, or small words
        if len(token) < 3:
            return False

        # Skip all-uppercase tokens to preserve acronyms and uppercase business terms (e.g. UDYAM, FSSAI, NET, USD)
        if token.isupper():
            return False

        # Skip hyphenated enterprise phrases (e.g. in-house, co-invest)
        if "-" in token:
            return False

        # Check if it's purely alphabetical with optional hyphens or apostrophes
        return bool(re.match(r"^[A-Za-z]+['-]?[A-Za-z]*$", token))

    def correct_word(self, word: str) -> str:
        """
        Corrects a single word if it meets the correction criteria.

        Args:
            word (str): Input word.

        Returns:
            str: Corrected word, or the original word if no corrections are found/applicable.
        """
        if not self._should_correct(word):
            return word

        # Maintain original capitalization profile (title case, lower, etc.)
        is_title = word.istitle()
        is_upper = word.isupper()

        # Query SymSpell suggestions
        suggestions = self.sym_spell.lookup(
            word.lower(), Verbosity.CLOSEST, max_edit_distance=2
        )

        if suggestions:
            corrected = suggestions[0].term
            if is_upper:
                return corrected.upper()
            if is_title:
                return corrected.capitalize()
            return corrected

        return word

    def correct_text(self, text: str) -> str:
        """
        Corrects standard English words in a multi-line paragraph or document
        while preserving spacing, line endings, and alphanumeric identifiers.

        Args:
            text (str): Input text containing multiple sentences/lines.

        Returns:
            str: Spell-corrected text.
        """
        if not text:
            return ""

        # Regular expression splits words (alphabetic sequences) while matching whitespace, numbers and punctuation
        tokens = re.split(r"(\b[A-Za-z]+['-]?[A-Za-z]*\b)", text)
        corrected_tokens = []

        for token in tokens:
            # Check if this token matches our word definition
            if re.match(r"^[A-Za-z]+['-]?[A-Za-z]*$", token):
                corrected_tokens.append(self.correct_word(token))
            else:
                # Keep whitespace, punctuation, and non-alphabetic strings intact
                corrected_tokens.append(token)

        return "".join(corrected_tokens)


# Example usage block
if __name__ == "__main__":
    corrector = SpellingCorrector()
    test_text = "The Invoce from Googl Inc for INV-9923 was sent on Wenesday. Total due: $1,250.40."
    print(f"Original: {test_text}")
    print(f"Corrected: {corrector.correct_text(test_text)}")
