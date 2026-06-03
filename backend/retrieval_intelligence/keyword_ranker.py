import json
import logging
import os
import re
import math
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

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

ENTERPRISE_TERMS: Set[str] = {
    "msme", "udyam", "fssai", "gst", "foscos", "onboarding", "in-house"
}

class KeywordRanker:
    """
    A standalone, native Python BM25 ranker for local document chunks.
    Builds statistics from metadata.json and computes BM25 scores with soft acronym support.
    """

    def __init__(self, metadata_path: str = None, k1: float = 1.5, b: float = 0.75) -> None:
        """
        Initializes the KeywordRanker and indexes the corpus from metadata.json.
        """
        if metadata_path is None:
            # Default to backend/embeddings/metadata.json
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            metadata_path = os.path.join(base_dir, "embeddings", "metadata.json")

        self.metadata_path = os.path.abspath(metadata_path)
        self.k1 = k1
        self.b = b

        self.chunks: List[Dict[str, Any]] = []
        self.doc_lens: Dict[str, int] = {}
        self.doc_term_freqs: Dict[str, Dict[str, int]] = {}
        self.doc_texts: Dict[str, str] = {}
        self.df: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.avgdl: float = 0.0
        self.num_docs: int = 0

        self._load_and_index_corpus()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenizes text into lowercase words, including hyphens/underscores."""
        if not text:
            return []
        return re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())

    def _load_and_index_corpus(self) -> None:
        """Loads corpus metadata and builds BM25 indexes."""
        if not os.path.exists(self.metadata_path):
            logger.warning(f"Metadata file not found at: {self.metadata_path}. BM25 ranker is unindexed.")
            return

        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.chunks = json.load(f)
            logger.info(f"Loaded {len(self.chunks)} chunks from {self.metadata_path} for BM25 indexing.")
        except Exception as e:
            logger.error(f"Failed to load metadata json for BM25: {e}")
            return

        self.num_docs = len(self.chunks)
        if self.num_docs == 0:
            logger.warning("Empty chunk list loaded. BM25 will return zero scores.")
            return

        total_len = 0
        for chunk in self.chunks:
            chunk_id = chunk["chunk_id"]
            text = chunk.get("text", "")
            self.doc_texts[chunk_id] = text

            tokens = self._tokenize(text)
            self.doc_lens[chunk_id] = len(tokens)
            total_len += len(tokens)

            # Calculate term frequencies within this document
            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self.doc_term_freqs[chunk_id] = tf

            # Track doc frequencies across the corpus
            for token in tf.keys():
                self.df[token] = self.df.get(token, 0) + 1

        self.avgdl = total_len / self.num_docs
        logger.info(f"BM25 indexing complete. Num docs: {self.num_docs}, avgdl: {self.avgdl:.2f}")

        # Precompute standard BM25 IDF for all known terms
        for term, doc_freq in self.df.items():
            # Standard BM25 IDF formulation:
            idf_val = math.log((self.num_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
            self.idf[term] = max(0.0, idf_val)

    def get_term_frequency(self, term: str, chunk_id: str) -> float:
        """
        Gets term frequency in a chunk with exact matching and soft acronym/enterprise substring fallback.
        """
        term = term.lower()
        tf_dict = self.doc_term_freqs.get(chunk_id, {})
        
        # Exact match frequency
        tf = float(tf_dict.get(term, 0))

        # Check soft substring matches for enterprise terms
        if term in ENTERPRISE_TERMS:
            # Check if term is a substring in the raw text or if it matches hyphenated variants
            text = self.doc_texts.get(chunk_id, "").lower()
            # Find occurrences as substring
            sub_count = text.count(term)
            if sub_count > tf:
                # Use sub_count to boost/reinforce matches
                tf = float(sub_count)

        return tf

    def get_idf(self, term: str) -> float:
        """Gets the IDF of a term. If term is unknown, computes default low IDF."""
        term = term.lower()
        if term in self.idf:
            return self.idf[term]
        
        # For unseen terms, we compute a conservative default IDF
        # treating it as if it appeared in 1 document
        idf_val = math.log((self.num_docs - 1 + 0.5) / (1 + 0.5) + 1.0)
        return max(0.0, idf_val)

    def score_query(self, query: str, candidate_chunk_ids: List[str]) -> Dict[str, float]:
        """
        Scores a list of candidate chunk IDs against a preprocessed query.
        Returns a dictionary mapping chunk_id to its normalized BM25 score [0.0, 1.0].
        """
        # Extract query terms, ignoring standard stopwords
        raw_tokens = self._tokenize(query)
        query_terms = [t for t in raw_tokens if t not in STOPWORDS]

        if not query_terms:
            # Fallback to including stopwords if query contains only stopwords
            query_terms = raw_tokens

        if not query_terms or not candidate_chunk_ids:
            return {cid: 0.0 for cid in candidate_chunk_ids}

        raw_scores = {}
        for cid in candidate_chunk_ids:
            if cid not in self.doc_lens:
                raw_scores[cid] = 0.0
                continue

            doc_len = self.doc_lens[cid]
            score = 0.0
            
            for q_term in query_terms:
                tf = self.get_term_frequency(q_term, cid)
                if tf == 0:
                    continue

                idf = self.get_idf(q_term)
                
                # BM25 formula:
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avgdl or 1.0)))
                score += idf * (numerator / denominator)

            raw_scores[cid] = score

        # Max-normalize the raw BM25 scores
        max_score = max(raw_scores.values()) if raw_scores else 0.0
        if max_score <= 0.0:
            return {cid: 0.0 for cid in candidate_chunk_ids}

        return {cid: raw_score / max_score for cid, raw_score in raw_scores.items()}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ranker = KeywordRanker()
    # Simple self-test
    if ranker.chunks:
        test_cids = [c["chunk_id"] for c in ranker.chunks[:5]]
        scores = ranker.score_query("FSSAI active status check", test_cids)
        print("BM25 scores:", scores)
    else:
        print("No chunks found. Run verify_embeddings.py first.")
