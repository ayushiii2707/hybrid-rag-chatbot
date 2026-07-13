import logging
import os
import re
import sys
from typing import Set
from symspellpy import SymSpell, Verbosity

# Bootstrap root path to ensure imports like 'backend' work in standalone scripts
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROOT_DIR = os.path.dirname(_BACKEND_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

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

        # Automatically discover and refresh enterprise vocabulary on instantiation
        self.refresh_enterprise_vocabulary(None)

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
        Ensures enterprise-specific terms are never altered.

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

        protected_detected = []
        terms_corrected = []
        terms_skipped = []

        for token in tokens:
            # Check if this token matches our word definition
            if re.match(r"^[A-Za-z]+['-]?[A-Za-z]*$", token):
                token_lower = token.lower()
                is_protected = token_lower in self.ignored_words or not self._should_correct(token)
                
                if is_protected:
                    if token_lower in self.ignored_words:
                        protected_detected.append(token)
                    terms_skipped.append(token)
                    corrected_tokens.append(token)
                else:
                    corrected = self.correct_word(token)
                    if corrected.lower() != token_lower:
                        terms_corrected.append(f"{token}->{corrected}")
                    corrected_tokens.append(corrected)
            else:
                # Keep whitespace, punctuation, and non-alphabetic strings intact
                corrected_tokens.append(token)

        # Developer logging
        if protected_detected or terms_corrected or terms_skipped:
            logger.info(
                f"[SpellingCorrector] Original Query: '{text}' | "
                f"Protected terms detected: {list(set(protected_detected))} | "
                f"Terms corrected: {terms_corrected} | "
                f"Terms skipped (protected): {list(set(terms_skipped))}"
            )

        return "".join(corrected_tokens)

    def refresh_enterprise_vocabulary(self, retrieval_engine=None) -> None:
        """
        Discovers and updates the protected enterprise vocabulary from system assets:
        - Tier 1: Section/subsection titles, metadata fields (from chunks/metadata.json)
        - Tier 2: Historically successful enterprise queries (from logs)
        - Tier 3: Frequently occurring chunk terms (document frequency >= 2)
        """
        logger.info("[SpellingCorrector] Refreshing enterprise vocabulary...")
        
        corpus_words = set()
        protected_terms = set()

        # Helper to validate a clean word (filters out noise, hashes, UUIDs, short tokens, digits, timestamps)
        def _is_clean_enterprise_word(w: str) -> bool:
            if len(w) < 3 or len(w) > 25:
                return False
            if not w.isalpha():
                return False
            # Must contain at least one vowel to ignore random consonant-only noise
            w_lower = w.lower()
            if not any(c in "aeiouy" for c in w_lower):
                return False
            # Filter out hex/hash patterns (like abcdef strings or random characters)
            if len(w_lower) >= 8 and all(c in "abcdef" for c in w_lower):
                return False
            return True

        # Tier 3 Default Base Ignored Config List
        base_ignored = ["UDYAM", "FSSAI", "GST", "MSME", "PAN", "onboarding", "in-house", "micr"]
        try:
            import json
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                ignored = config_data.get("spelling_corrector", {}).get("ignored_words", [])
                for w in ignored:
                    base_ignored.append(w)
        except Exception as e:
            logger.warning(f"Could not load ignored words from config.json: {e}")

        # Explicit enterprise vocabulary from requirements
        explicit_vocab = [
            "GST", "GSTIN", "PAN", "FSSAI", "MSME", "UDYAM", "Vendor", "Supplier",
            "Reliance", "PO", "SKU", "HSN", "SAC", "FBO", "UDYAG", "UDYOG", "FosCos",
            "onboarding", "in-house", "MICR", "micr"
        ]
        for w in explicit_vocab:
            base_ignored.append(w)

        for w in base_ignored:
            w_lower = w.lower()
            protected_terms.add(w_lower)
            corpus_words.add(w_lower)

        # Helper to extract potential enterprise terms from a text span
        def extract_candidates(text_span: str, dest_protected: set, dest_corpus: set):
            if not text_span or not isinstance(text_span, str):
                return
            words = re.findall(r"\b[A-Za-z]+['-]?[A-Za-z]*\b", text_span)
            for w in words:
                if not _is_clean_enterprise_word(w):
                    continue
                w_lower = w.lower()
                dest_corpus.add(w_lower)
                
                is_upper = w.isupper()
                is_title = w.istitle()
                is_standard = w_lower in self.sym_spell.words if hasattr(self, "sym_spell") and self.sym_spell else True
                
                if is_upper or (is_title and not is_standard) or not is_standard:
                    dest_protected.add(w_lower)

        # Load chunks from database or retrieval_engine
        chunks = []
        if retrieval_engine and hasattr(retrieval_engine, "keyword_ranker") and hasattr(retrieval_engine.keyword_ranker, "chunks"):
            chunks = retrieval_engine.keyword_ranker.chunks
        else:
            try:
                from backend.database.db import SessionLocal
                from backend.auth.auth_models import Chunk, Document
                db = SessionLocal()
                try:
                    db_chunks = db.query(Chunk).all()
                    for c in db_chunks:
                        doc = db.query(Document).filter(Document.id == c.doc_id).first()
                        chunks.append({
                            "chunk_id": c.chunk_id,
                            "doc_id": c.doc_id,
                            "text": c.text,
                            "source_file": doc.source_file if doc else "",
                            "page_number": c.page_number,
                            "chunk_index": c.chunk_index,
                            "metadata": {
                                "section_title": c.section_title,
                                "subsection_title": c.subsection_title,
                                "procedure_id": c.procedure_id,
                                "alternate_phrasings": c.alternate_phrasings or []
                            }
                        })
                    logger.info(f"[SpellingCorrector] Loaded {len(chunks)} chunks from database for vocabulary discovery.")
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Could not load chunks from database directly: {e}")

        # TIER 1: Section Titles, Subsection Titles, Metadata Fields
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            extract_candidates(meta.get("section_title", ""), protected_terms, corpus_words)
            extract_candidates(meta.get("subsection_title", ""), protected_terms, corpus_words)
            extract_candidates(meta.get("procedure_id", ""), protected_terms, corpus_words)
            extract_candidates(meta.get("source_file", ""), protected_terms, corpus_words)

        # TIER 2: Historically successful enterprise queries
        log_queries = []
        try:
            from backend.database.db import SessionLocal
            from backend.auth.auth_models import QueryLog
            db = SessionLocal()
            try:
                logs = db.query(QueryLog).filter(
                    QueryLog.answer_found == True,
                    QueryLog.confidence >= 0.55
                ).all()
                for log in logs:
                    q_text = log.corrected_query if log.corrected_query else log.query
                    if q_text:
                        log_queries.append(q_text)
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Could not load queries from DB QueryLog: {e}")

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_file = os.path.join(backend_dir, "logs", "query_logs.jsonl")
        if os.path.exists(log_file):
            try:
                import json
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            log_data = json.loads(line)
                            if log_data.get("answer_found") is True and log_data.get("confidence", 0.0) >= 0.55:
                                q_text = log_data.get("corrected_query") if log_data.get("corrected_query") else log_data.get("query")
                                if q_text:
                                    log_queries.append(q_text)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Could not read local query logs file: {e}")

        for q in log_queries:
            extract_candidates(q, protected_terms, corpus_words)

        # TIER 3: Frequently Occurring Chunk Terms (document frequency >= N, where N=2)
        chunk_word_counts = {}
        for chunk in chunks:
            text = chunk.get("text", "")
            if text:
                # Get unique words per chunk to count document frequency
                words_in_chunk = set(re.findall(r"\b[A-Za-z]+['-]?[A-Za-z]*\b", text))
                for w in words_in_chunk:
                    if _is_clean_enterprise_word(w):
                        w_lower = w.lower()
                        chunk_word_counts[w_lower] = chunk_word_counts.get(w_lower, 0) + 1

        for w_lower, count in chunk_word_counts.items():
            if count >= 2:  # Must appear in >= 2 chunks
                is_standard = w_lower in self.sym_spell.words if hasattr(self, "sym_spell") and self.sym_spell else True
                if not is_standard:
                    # Prefer noun-like enterprise terms: non-standard words (e.g. fssai, udyam) are added to protected list
                    protected_terms.add(w_lower)
                # Boost all frequently occurring chunk terms in SymSpell frequency dictionary
                corpus_words.add(w_lower)

        # Update ignored_words set with protected enterprise vocabulary
        self.ignored_words.update(protected_terms)

        # Register ALL discovered corpus words in SymSpell to bias typo corrections
        if hasattr(self, "sym_spell") and self.sym_spell:
            for word in corpus_words:
                if word.isalpha():
                    try:
                        self.sym_spell.create_dictionary_entry(word, 1000000000)
                    except Exception:
                        pass


        logger.info(
            f"[SpellingCorrector] Enterprise vocabulary refreshed. "
            f"Total protected terms: {len(self.ignored_words)} | "
            f"Total registered corpus/domain words: {len(corpus_words)}"
        )


# Example usage block
if __name__ == "__main__":
    corrector = SpellingCorrector()
    test_text = "The Invoce from Googl Inc for INV-9923 was sent on Wenesday. Total due: $1,250.40."
    print(f"Original: {test_text}")
    print(f"Corrected: {corrector.correct_text(test_text)}")
