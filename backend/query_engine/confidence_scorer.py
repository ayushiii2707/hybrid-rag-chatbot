import logging
import re
from typing import Set

logger = logging.getLogger(__name__)

# Basic static stopwords list to maintain zero external network dependencies
STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "to", "for", 
    "in", "on", "at", "by", "of", "with", "about", "against", "between", "into", 
    "through", "during", "before", "after", "above", "below", "from", "up", "down", 
    "in", "out", "off", "over", "under", "again", "further", "then", "once", "here", 
    "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", 
    "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", 
    "same", "so", "than", "too", "very", "can", "will", "just", "should", "now", 
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she", "her", 
    "it", "its", "they", "them", "their", "this", "that", "these", "those"
}


class ConfidenceScorer:
    """
    Computes query retrieval confidence scores by evaluating FAISS semantic similarity,
    keyword overlap metrics, and semantic sentence density inside the target chunk.
    """

    def __init__(self) -> None:
        pass

    def _extract_keywords(self, text: str) -> Set[str]:
        """Tokenizes text and extracts unique lowercase alphanumeric keywords, filtering stopwords."""
        if not text:
            return set()
        words = re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())
        return {w for w in words if w not in STOPWORDS}

    def compute_confidence(
        self,
        query: str,
        chunk_text: str,
        similarity_score: float,
        excerpt_density_score: float
    ) -> float:
        """
        Calculates a unified confidence rating between 0.0 and 1.0.

        Args:
            query (str): Preprocessed user search query.
            chunk_text (str): Verbatim text of the best matching chunk.
            similarity_score (float): Cosine similarity score from FAISS index search.
            excerpt_density_score (float): Best sentence-level cosine similarity score.

        Returns:
            float: Confidence score bounded between 0.0 and 1.0.
        """
        if not query or not chunk_text:
            return 0.0

        # 1. Compute Keyword Overlap
        query_kws = self._extract_keywords(query)
        chunk_text_lower = chunk_text.lower()

        if not query_kws:
            # If query has only stopwords/empty, bypass keyword overlap penalty
            keyword_overlap = 1.0
        else:
            matched_kws = sum(1 for kw in query_kws if kw in chunk_text_lower)
            keyword_overlap = matched_kws / len(query_kws)

        # 2. Heuristic Combination
        # Similarity: weights 0.5
        # Keyword Overlap: weights 0.3
        # Excerpt Density: weights 0.2
        confidence = (0.5 * similarity_score) + (0.3 * keyword_overlap) + (0.2 * excerpt_density_score)

        # 3. Apply Penalties
        # Strict Penalty: if there is absolute zero keyword overlap on significant words, heavily penalize confidence
        if keyword_overlap == 0.0 and len(query_kws) > 0:
            confidence *= 0.5
            logger.info("Confidence penalized: 0% keyword overlap with target chunk.")

        # Ensure bounds
        confidence = max(0.0, min(1.0, confidence))

        logger.info(
            f"Confidence calculated: similarity={similarity_score:.4f}, keyword_overlap={keyword_overlap:.4f}, "
            f"density={excerpt_density_score:.4f} -> Final Confidence: {confidence:.4f}"
        )

        return float(confidence)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scorer = ConfidenceScorer()
    q = "FSSAI active status check"
    txt = "You may check the Active/Inactive status of FSSAI License from the portal link."
    score = scorer.compute_confidence(q, txt, 0.7075, 0.8123)
    print("Confidence:", score)
