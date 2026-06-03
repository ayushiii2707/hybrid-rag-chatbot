import logging
from typing import Any, Dict, List, Optional
import spacy
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class EntityMatcher:
    """
    A production-grade component combining spaCy (for Named Entity Recognition)
    and RapidFuzz (for fuzzy string matching) to identify and normalize key entities,
    specifically focusing on matching organization names against a known reference vendor list.
    """

    def __init__(
        self,
        spacy_model: str = "en_core_web_sm",
        reference_vendors: List[str] = None,
    ) -> None:
        """
        Initializes the EntityMatcher with a spaCy model and a vendor reference list.

        Args:
            spacy_model (str): The name of the spaCy model to load (default: "en_core_web_sm").
            reference_vendors (List[str], optional): Reference list of known vendor names.
        """
        try:
            self.nlp = spacy.load(spacy_model)
            logger.info(f"spaCy model '{spacy_model}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load spaCy model '{spacy_model}': {e}")
            raise RuntimeError(f"Could not load spaCy model: {spacy_model}") from e

        # Load configuration from config.json relative to this file
        import os
        import json

        self.matching_threshold = 80.0
        self.max_org_words = 4
        self.max_word_diff = 2
        self.generic_phrases = []
        config_vendors = None

        try:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                em_config = config_data.get("entity_matcher", {})
                self.matching_threshold = em_config.get("matching_threshold", 80.0)
                self.max_org_words = em_config.get("max_org_words", 4)
                self.max_word_diff = em_config.get("max_word_diff", 2)
                config_vendors = em_config.get("reference_vendors", None)
                self.generic_phrases = em_config.get("generic_phrases", [])
                logger.info("Loaded EntityMatcher configuration from config.json.")
        except Exception as e:
            logger.warning(f"Could not load EntityMatcher config from config.json: {e}")

        # Set reference vendors
        if reference_vendors is not None:
            self.reference_vendors = reference_vendors
        elif config_vendors is not None:
            self.reference_vendors = config_vendors
        else:
            self.reference_vendors = [
                "Google",
                "Microsoft",
                "Amazon Web Services",
                "Apple",
                "Oracle",
                "Salesforce",
                "Intel Corp",
                "Dell Technologies",
                "Hewlett Packard",
                "Cisco Systems",
                "IBM Corp",
                "Adobe Inc",
                "Zoom",
            ]

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts named entities from the text using spaCy.

        Args:
            text (str): Input normalized text.

        Returns:
            List[Dict[str, Any]]: List of dictionary entities containing metadata:
                {
                    "text": str,
                    "label": str,
                    "start_char": int,
                    "end_char": int
                }
        """
        if not text:
            return []

        doc = self.nlp(text)
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text.strip(),
                "label": ent.label_,
                "start_char": ent.start_char,
                "end_char": ent.end_char
            })
        return entities

    def _validate_match(self, org_name: str, matched_vendor: str) -> bool:
        """
        Validates a fuzzy match to prevent false positives using word-count differences,
        word overlap, and generic phrase detection.
        """
        org_clean = org_name.strip()
        
        # 1. Prevent generic phrases from matching vendors
        for phrase in self.generic_phrases:
            if phrase.lower() == org_clean.lower() or org_clean.lower().startswith(phrase.lower() + " ") or org_clean.lower().endswith(" " + phrase.lower()):
                logger.info(f"Match rejected: '{org_name}' matches/contains generic phrase '{phrase}'")
                return False

        # Tokenize and filter out common corporate/filler words
        org_words = [w.strip(",.()\"'") for w in org_clean.split() if w.strip(",.()\"'")]
        vendor_words = [w.strip(",.()\"'") for w in matched_vendor.split() if w.strip(",.()\"'")]
        
        ignored_fillers = {"inc", "corp", "co", "ltd", "limited", "corporation", "incorporated", "of", "and", "systems", "technologies", "services", "web"}
        org_words_filtered = [w for w in org_words if w.lower() not in ignored_fillers]
        vendor_words_filtered = [w for w in vendor_words if w.lower() not in ignored_fillers]

        # 2. Word-count validation guard
        if len(org_words_filtered) > self.max_org_words:
            logger.info(f"Match rejected: '{org_name}' has too many words ({len(org_words_filtered)} > {self.max_org_words})")
            return False
            
        word_diff = abs(len(org_words_filtered) - len(vendor_words_filtered))
        if word_diff > self.max_word_diff:
            logger.info(f"Match rejected: word count difference too large between '{org_name}' and '{matched_vendor}' ({word_diff} > {self.max_word_diff})")
            return False

        # 3. Fuzzy overlap validation guard
        has_overlap = False
        for vw in vendor_words_filtered:
            vw_lower = vw.lower()
            for ow in org_words_filtered:
                ow_lower = ow.lower()
                if ow_lower == vw_lower or (len(ow_lower) >= 3 and ow_lower in vw_lower) or (len(vw_lower) >= 3 and vw_lower in ow_lower):
                    has_overlap = True
                    break
            if has_overlap:
                break
                
        if not has_overlap:
            logger.info(f"Match rejected: no word overlap/similarity between '{org_name}' and '{matched_vendor}'")
            return False

        return True

    def match_vendor(self, org_name: str, threshold: float = None) -> Optional[str]:
        """
        Uses RapidFuzz to match an extracted organization name against the reference vendor list,
        applying configured threshold and validation guards.

        Args:
            org_name (str): The extracted organization name to match.
            threshold (float, optional): The matching confidence threshold (0.0 to 100.0).
                                        If None, defaults to the configured matching_threshold.

        Returns:
            Optional[str]: The normalized matching vendor name, or None if confidence is too low or validation fails.
        """
        if not org_name or not self.reference_vendors:
            return None

        if threshold is None:
            threshold = self.matching_threshold

        # WRatio (Weighted Ratio) handles substrings and case differences gracefully
        match = process.extractOne(
            org_name,
            self.reference_vendors,
            scorer=fuzz.WRatio,
            score_cutoff=threshold
        )

        if match:
            matched_str, score, _ = match
            if self._validate_match(org_name, matched_str):
                logger.info(
                    f"Fuzzy matched ORG '{org_name}' to Vendor '{matched_str}' (Confidence: {score:.2f}%)"
                )
                return matched_str
            else:
                logger.info(
                    f"Fuzzy match of '{org_name}' to Vendor '{matched_str}' (Confidence: {score:.2f}%) failed validation guards."
                )

        return None

    def resolve_vendors_from_text(self, text: str, threshold: float = None) -> List[str]:
        """
        Helper method to extract all ORG entities from text and resolve them to vendor matches.

        Args:
            text (str): Input normalized text.
            threshold (float, optional): Confidence threshold for vendor matching.

        Returns:
            List[str]: List of unique resolved vendor names.
        """
        entities = self.extract_entities(text)
        matched_vendors = []
        for ent in entities:
            if ent["label"] == "ORG":
                match = self.match_vendor(ent["text"], threshold=threshold)
                if match and match not in matched_vendors:
                    matched_vendors.append(match)
        return matched_vendors


# Example usage block
if __name__ == "__main__":
    matcher = EntityMatcher()
    sample = "We received a billing statement from Amazon Web Srvcs for $5,000 and another from Microsoft Corp."
    print(f"Sample: '{sample}'")
    entities = matcher.extract_entities(sample)
    print("\nExtracted Entities:")
    for e in entities:
        print(f" - {e['text']} ({e['label']})")

    resolved = matcher.resolve_vendors_from_text(sample)
    print(f"\nResolved Vendors: {resolved}")
