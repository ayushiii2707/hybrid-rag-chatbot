import logging
import os
import re
import sys
from typing import Any, Dict, List
import numpy as np

logger = logging.getLogger(__name__)

# ── Bootstrap Paths ───────────────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))

try:
    from embedding_generator import EmbeddingGenerator
except ImportError as e:
    logger.critical(f"Failed to import EmbeddingGenerator: {e}")
    raise RuntimeError("Import failed in AnswerExtractor") from e


class AnswerExtractor:
    """
    Sentence-level Answer Extractor.
    Extracts verbatim semantic regions/excerpts from the retrieved chunk text.
    It does not generate text, avoiding any potential LLM hallucinations.
    """

    def __init__(self, generator: EmbeddingGenerator, sentence_split_regex: str = None) -> None:
        """
        Initializes the AnswerExtractor.

        Args:
            generator (EmbeddingGenerator): Initialized EmbeddingGenerator.
            sentence_split_regex (str, optional): Regex pattern to segment text into sentences.
        """
        self.generator = generator
        # Default regex pattern: split on periods, exclamation marks, or question marks followed by space
        self.sentence_split_regex = sentence_split_regex or r"(?<=[.!?])\s+"

    def extract_answer_excerpt(self, query_vector: np.ndarray, chunk_text: str) -> Dict[str, Any]:
        """
        Splits chunk text into sentences, computes semantic similarity for each sentence,
        and returns the most relevant verbatim excerpt along with its similarity density score.

        Args:
            query_vector (np.ndarray): 1D query embedding of shape (dimension,).
            chunk_text (str): The raw text of the matching document chunk.

        Returns:
            Dict[str, Any]: Dictionary containing excerpt details:
                {
                    "excerpt": str,
                    "density_score": float
                }
        """
        if not chunk_text or not chunk_text.strip():
            return {"excerpt": "", "density_score": 0.0}

        # 1. Segment chunk into sentences
        raw_sentences = re.split(self.sentence_split_regex, chunk_text)
        sentences = [s.strip() for s in raw_sentences if s.strip()]

        if not sentences:
            return {"excerpt": chunk_text, "density_score": 0.0}

        # 2. Generate embeddings for each sentence
        try:
            sentence_embeddings = self.generator.generate_embeddings(sentences)
        except Exception as e:
            logger.error(f"Failed to generate sentence embeddings in AnswerExtractor: {e}")
            return {"excerpt": sentences[0], "density_score": 0.0}

        if sentence_embeddings.shape[0] == 0:
            return {"excerpt": sentences[0], "density_score": 0.0}

        # 3. Calculate cosine similarity between query and each sentence embedding
        # Normalize sentence embeddings
        s_norms = np.linalg.norm(sentence_embeddings, axis=1, keepdims=True)
        s_norms[s_norms == 0] = 1e-10  # Avoid division by zero
        norm_s = sentence_embeddings / s_norms

        # Normalize query vector
        q_norm = np.linalg.norm(query_vector)
        q_norm = q_norm if q_norm > 0 else 1e-10
        norm_q = query_vector / q_norm

        # Dot product of normalized vectors
        similarities = np.dot(norm_s, norm_q)

        # 4. Identify best matching sentence index
        best_idx = int(np.argmax(similarities))
        best_sentence = sentences[best_idx]
        best_score = float(similarities[best_idx])

        # 5. Extract excerpt context (include adjacent sentence if target is short)
        is_faq = (
            "answer:" in chunk_text.lower() or
            "question:" in chunk_text.lower()
        )
        if is_faq:
            excerpt = chunk_text.strip()
        else:
            excerpt = best_sentence
            if len(best_sentence) < 150 and best_idx + 1 < len(sentences):
                excerpt = f"{best_sentence} {sentences[best_idx + 1]}"

        logger.info(
            f"Extracted answer excerpt (density={best_score:.4f}): '{excerpt[:100]}...'"
        )

        return {
            "excerpt": excerpt,
            "density_score": best_score
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gen = EmbeddingGenerator()
    extractor = AnswerExtractor(generator=gen)
    q_vec = gen.generate_embeddings(["billing statement from Amazon Web Services"])[0]
    sample_text = (
        "Add Delivery Location. Merchandise Supplier refers to Supplier of Goods. "
        "Articles intended for in-house consumption are not supported. "
        "We received a billing statement from Amazon Web Services for $5,000. "
        "Contact coordinates on the map."
    )
    result = extractor.extract_answer_excerpt(q_vec, sample_text)
    print("Excerpt:", result["excerpt"])
    print("Score:", result["density_score"])
