import logging
import os
import re
import sys
from typing import Any, Dict, List

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

    # ── Enterprise Synonym Expansion Map (Problem 9) ─────────────────────────
    # Deterministic, domain-locked mapping.  Keys are normalised lowercase.
    # Each value is a list of expansion terms that will be APPENDED to the retrieval
    # query only — QueryGuard and Suggestion layer always see the plain corrected query.
    ENTERPRISE_SYNONYM_MAP: Dict[str, List[str]] = {
        # ─ PAN / National Identity ────────────────────────────────────────
        "pan": ["permanent account number"],
        "permanent account number": ["pan"],
        "national identity card": ["pan", "permanent account number", "supplier pan details"],
        "national identity card number": ["pan", "permanent account number", "supplier pan details"],
        "pan identification": ["pan", "permanent account number", "supplier pan details"],
        "pan identification number": ["pan", "permanent account number", "supplier pan details"],
        "tax identity number": ["pan", "permanent account number", "supplier pan details"],
        # ─ GST / Tax Registry ────────────────────────────────────────
        "gst": ["goods and services tax", "gstin"],
        "gstin": ["gst", "goods and services tax"],
        "goods and services tax": ["gst", "gstin"],
        "tax registry number": ["gst", "gstin", "goods and services tax", "gstin details bank account", "GSTIN number should belong to the respective state If vendor is GST registered No GSTIN declaration form"],
        "tax identification data": ["pan", "gst", "permanent account number", "gstin details bank account"],
        "tax registration number": ["gst", "gstin"],
        "gst registration data": ["gst", "gstin", "goods and services tax"],
        "tax registry": ["gst", "gstin"],
        # ─ FSSAI / Food Safety ───────────────────────────────────────
        "fssai": ["food safety license", "food safety and standards authority of india", "fbo"],
        "food safety license": ["fssai"],
        "food safety approval": ["fssai", "food safety license"],
        "food safety registry": ["fssai", "food safety license"],
        "safety license": ["fssai", "food safety license", "fssai details active inactive status portal link tips focus fssai gov in"],
        "safety license of food products": ["fssai", "food safety license", "fssai details active inactive status portal link tips focus fssai gov in"],
        "food license": ["fssai", "food safety license"],
        "fbo": ["food business operator", "fssai"],
        "fssai registry": ["fssai", "food safety license"],
        # ─ MSME / Small Business ──────────────────────────────────────
        "msme": ["small business registration", "micro small medium enterprise", "udyam"],
        "udyam": ["msme", "udyam registration"],
        "micro small medium enterprise": ["msme", "udyam"],
        "small business registration": ["msme"],
        "micro enterprise": ["msme", "micro small medium enterprise", "udyam"],
        "micro enterprise status": ["msme", "udyam"],
        "small enterprise": ["msme", "micro small medium enterprise"],
        # ─ MICR / Bank Routing ───────────────────────────────────────
        "micr": ["bank routing code", "magnetic ink character recognition", "ifsc code bank details", "Account Number Valid bank account number IFSC Code Valid IFSC code of the bank Bank Name Branch Name Bank Document"],
        "bank routing code": ["micr", "ifsc code bank details"],
        "bank routing codes": ["micr", "bank routing code", "ifsc code bank details"],
        "routing code": ["micr", "bank routing code", "ifsc code bank details"],
        "routing number": ["micr", "bank routing code", "ifsc code bank details"],
        "bank routing": ["micr", "ifsc code bank details"],
        # ─ IFSC ─────────────────────────────────────────────────────────
        "ifsc": ["bank branch code", "indian financial system code"],
        "indian financial system code": ["ifsc"],
        # ─ Vendor / Supplier Registration ────────────────────────────────
        "onboarding": ["vendor registration", "supplier registration"],
        "vendor registration": ["onboarding", "supplier registration"],
        "supplier registration": ["onboarding", "vendor registration"],
        "supplier registration application": ["vendor registration", "onboarding"],
        "onboarding application": ["vendor registration", "supplier registration", "request id generation approval"],
        "onboarding process": ["vendor registration", "supplier registration", "onboarding", "registration steps", "registration flow"],
        "vendor onboarding": ["vendor registration", "onboarding", "supplier registration"],
        "registration flow": ["registration process", "registration steps", "onboarding process", "onboarding steps", "steps in the registration"],
        "onboarding flow": ["registration process", "registration steps", "onboarding process", "onboarding steps", "steps in the registration"],
        "registration process": ["registration steps", "registration flow", "onboarding process"],
        "flow": ["process", "steps", "workflow"],
        "stages of supplier onboarding": ["registration steps", "registration process", "onboarding steps", "onboarding process"],
        "stages of registration": ["registration steps", "registration process", "onboarding steps", "onboarding process"],
        "stages": ["steps", "process", "flow", "workflow"],
        "stage": ["step", "process", "flow", "workflow"],
        "submit onboarding application": ["submit form", "final submission", "request id generation approval"],
        # ─ Delivery / Physical Address ───────────────────────────────────
        "delivery location": ["delivery address", "shipment location", "delivery site"],
        "physical address": ["delivery location", "delivery address", "shipment location"],
        "delivery center": ["delivery location", "warehouse", "shipment location"],
        "shipment location": ["delivery location", "delivery address"],
        "delivery site": ["delivery location", "delivery address"],
        # ─ Portal / Access ──────────────────────────────────────────────
        "onboarding portal": ["supplier portal", "registration portal", "vendor portal", "login credentials activation email request id generation"],
        "supplier portal": ["onboarding portal", "registration portal"],
        "registration portal": ["onboarding portal", "supplier portal"],
        # ─ Status / Validation ─────────────────────────────────────────
        "active status": ["licence status", "registration status"],
        "invalid": ["verification failed", "incorrect status", "not valid", "failed checks"],
        "validation failed": ["invalid"],
        "submission progress": ["submit form", "submit application", "request id", "application status", "submit the form request id generation"],
        "business approval": ["request id generation", "approval notification", "verification status", "registration approval auto generated email activation link"],
        "contact detail fields": ["contact details", "contact information", "provide contact information detail"],
        "status report": ["verification status", "active status", "inactive status", "status of vendor registration status report tab"],
        "vendor status": ["registration status", "onboarding status", "status of vendor registration status report tab"],
        # ─ General Procurement ─────────────────────────────────────────
        "purchase order": ["po"],
        "po": ["purchase order"],
        "invoice": ["bill", "tax invoice"],
        "tax invoice": ["invoice"],
    }

    def expand_synonyms(self, query: str) -> str:
        """
        Appends synonym/expanded terms for enterprise vocabulary tokens found in *query*.
        Expansion is additive — original terms are never removed.

        Args:
            query (str): The typo-corrected query string.

        Returns:
            str: The query with any matched synonym expansions appended.
        """
        if not query or not query.strip():
            return query

        q_lower = query.lower()
        appended_terms: List[str] = []

        # 1. Dictionary-based synonym expansion
        # Match multi-word keys first (longest key first to avoid partial overlaps)
        sorted_keys = sorted(self.ENTERPRISE_SYNONYM_MAP.keys(), key=lambda k: -len(k.split()))
        covered_spans: List[tuple] = []  # (start, end) character spans already consumed

        for key in sorted_keys:
            pattern = re.compile(r'\b' + re.escape(key) + r'\b', re.IGNORECASE)
            for m in pattern.finditer(q_lower):
                span = (m.start(), m.end())
                # Skip if span overlaps with an already-matched longer key
                overlapping = any(
                    span[0] < cs[1] and span[1] > cs[0]
                    for cs in covered_spans
                )
                if not overlapping:
                    covered_spans.append(span)
                    for expansion_term in self.ENTERPRISE_SYNONYM_MAP[key]:
                        if expansion_term.lower() not in q_lower and expansion_term not in appended_terms:
                            appended_terms.append(expansion_term)

        # 2. Rule-based Semantic Intent Mapping (handles arbitrary alternative phrasings)
        def has_any(words):
            return any(w in q_lower for w in words)

        # -- PAN Validation Rules --
        if has_any(["pan", "permanent account number"]):
            if has_any(["rule", "format", "look", "structure", "validation", "criteria", "requirements", "valid", "length", "character"]):
                if not has_any(["upload", "file", "document", "pdf", "jpg"]):
                    for term in ["pan validation rules", "pan structure rules", "format of pan", "validation rules for pan"]:
                        if term not in appended_terms:
                            appended_terms.append(term)

        # -- GSTIN / GST Validation/Uniqueness --
        if has_any(["gst", "gstin"]):
            if has_any(["duplicate", "validation", "rules", "exist", "uniqueness", "check", "verify", "rule", "multiple"]):
                for term in ["duplicate gstin validation", "duplicate validation rules", "gstin validation rules"]:
                    if term not in appended_terms:
                        appended_terms.append(term)

        # -- FSSAI Active Status --
        if has_any(["fssai", "food safety"]):
            if has_any(["status", "active", "inactive", "check", "verify", "link", "portal"]):
                for term in ["active inactive status", "fssai active status", "fssai status check", "fssai verification"]:
                    if term not in appended_terms:
                        appended_terms.append(term)

        # -- UDYAM / MSME Validation/Verification --
        if has_any(["udyam", "msme"]):
            if has_any(["rule", "format", "verify", "check", "validation", "structure", "length", "issue", "validity", "character"]):
                for term in ["udyam validation rules", "udyam number format", "udyam verification", "udyam validity"]:
                    if term not in appended_terms:
                        appended_terms.append(term)

        # -- Registration Steps / Flow --
        if has_any(["registration", "onboarding", "onboard", "register"]):
            if has_any(["step", "steps", "flow", "stages", "stage", "process", "workflow", "procedure", "how"]):
                for term in ["registration steps", "registration process", "onboarding process", "registration flow", "stages of supplier onboarding"]:
                    if term not in appended_terms:
                        appended_terms.append(term)

        if appended_terms:
            expanded_query = query.strip() + " " + " ".join(appended_terms)
            logger.info(
                f"[SynonymExpansion] Original: '{query}' | "
                f"Expanded: '{expanded_query}' | "
                f"Appended: {appended_terms}"
            )
            return expanded_query

        return query

    def refresh_vocabulary(self, retrieval_engine=None) -> None:
        """
        Refreshes the spelling corrector's enterprise vocabulary using active retrieval engine assets.
        """
        if hasattr(self, "corrector") and hasattr(self.corrector, "refresh_enterprise_vocabulary"):
            self.corrector.refresh_enterprise_vocabulary(retrieval_engine)

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

        # Handle contextual "ad" -> "add" mapping
        cleaned_query = re.sub(r'\bad\b(?=\s+(?:delivery|location|product|vendor))', 'add', cleaned_query, flags=re.IGNORECASE)

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
