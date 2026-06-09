import json
import logging
import os
from typing import Any, Dict, List, Optional
from embeddings.embedding_generator import EmbeddingGenerator
from embeddings.vector_store import BaseVectorStore, FAISSVectorStore

logger = logging.getLogger(__name__)


def normalize_score(score: float) -> float:
    """Maps raw FAISS inner-product score to a clean 0.0–1.0 range."""
    return max(0.0, min(1.0, (score + 1) / 2))


class RetrievalEngine:
    """
    A production-grade semantic search retrieval engine.
    Orchestrates the query embedding generation, index lookup, and threshold filtering.
    Designed for integration with downstream APIs (e.g. FastAPI) and future LLM generation layers.
    """

    def __init__(
        self,
        generator: Optional[EmbeddingGenerator] = None,
        vector_store: Optional[BaseVectorStore] = None,
        config_path: str = None
    ) -> None:
        """
        Initializes the RetrievalEngine with configurations.

        Args:
            generator (EmbeddingGenerator, optional): Pre-initialized embedding generator.
            vector_store (BaseVectorStore, optional): Pre-initialized vector store.
            config_path (str, optional): Custom path to config.json.
        """
        # Load configuration parameters
        self.top_k = 3
        self.similarity_threshold = 0.25

        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                ret_config = config_data.get("retrieval", {})
                self.top_k = ret_config.get("top_k", self.top_k)
                self.similarity_threshold = ret_config.get("similarity_threshold", self.similarity_threshold)
                logger.info("Loaded RetrievalEngine configurations from config.json.")
            except Exception as e:
                logger.warning(f"Could not load retrieval settings from config: {e}")

        # Lazy initialize modules if not passed in
        self.generator = generator or EmbeddingGenerator(config_path=config_path)
        self.vector_store = vector_store or FAISSVectorStore(config_path=config_path)

        # Attempt to load index if files are available
        try:
            self.vector_store.load_index()
        except Exception as e:
            logger.warning(f"Could not load vector store index during initialization (it might start empty): {e}")

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes a semantic similarity query against the indexed documents.

        Args:
            query (str): Search text query.
            top_k (int, optional): Number of nearest neighbors to retrieve. Defaults to configured top_k.
            threshold (float, optional): Cosine similarity filter threshold (0.0 to 1.0).
                                         Defaults to configured similarity_threshold.

        Returns:
            List[Dict[str, Any]]: List of matching chunk dictionaries containing:
                {
                    "chunk_id": str,
                    "text": str,
                    "score": float,
                    "metadata": {
                        "doc_id": str,
                        "source_file": str,
                        "page_number": int,
                        "char_count": int
                    }
                }
        """
        if not query or not query.strip():
            logger.warning("Empty query received. Returning empty list.")
            return []

        search_k = top_k if top_k is not None else self.top_k
        filter_threshold = threshold if threshold is not None else self.similarity_threshold

        logger.info(
            f"Retrieving for query: '{query}' (top_k={search_k}, threshold={filter_threshold})"
        )

        # 1. Generate Query Vector Embedding
        query_vector = self.generator.generate_embeddings([query])[0]

        # 2. Query Vector Index
        raw_matches = self.vector_store.search(query_vector, top_k=search_k)

        # 3. Filter by similarity threshold
        filtered_matches = []
        rejected_count = 0
        for match in raw_matches:
            score = match["score"]
            if score >= filter_threshold:
                filtered_matches.append(match)
            else:
                rejected_count += 1
                logger.info(
                    f"Match '{match['chunk_id']}' rejected: score {score:.4f} is below threshold {filter_threshold}."
                )

        # Normalize scores to 0.0–1.0 range
        for r in filtered_matches:
            r["score"] = normalize_score(r["score"])

        logger.info(
            f"[RetrievalEngine] FAISS raw candidates: {len(raw_matches)}, "
            f"Rejected by threshold: {rejected_count}, "
            f"Surviving: {len(filtered_matches)} (threshold={filter_threshold})"
        )
        return filtered_matches


    def retrieve_candidate_chunks(
        self,
        query: str,
        top_k: Optional[int] = None,
        original_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves multiple candidate chunks (procedural / workflow queries)."""
        return self.retrieve(query, top_k=top_k)

    def retrieve_best_chunk(
        self,
        query: str,
        top_k: Optional[int] = None,
        original_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves the best matching chunk (factual / single-answer queries)."""
        return self.retrieve(query, top_k=top_k)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Basic check with empty index behavior
    engine = RetrievalEngine()
    results = engine.retrieve("Test search query")
    print("Search results on empty index:", results)
