import json
import logging
import os
from typing import Any, Dict, List
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    A production-grade embedding generator wrapping the local sentence-transformers model.
    Configured to generate embeddings from text chunks in batches.
    """

    def __init__(self, config_path: str = None) -> None:
        """
        Initializes the EmbeddingGenerator and loads the sentence-transformers model.

        Args:
            config_path (str, optional): Custom path to config.json. If None, resolves to the default relative path.
        """
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self.batch_size = 32

        # 1. Load config if present
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                emb_config = config_data.get("embedding", {})
                self.model_name = emb_config.get("model_name", self.model_name)
                self.batch_size = emb_config.get("batch_size", self.batch_size)
                logger.info(f"Loaded EmbeddingGenerator configuration from {config_path}")
            except Exception as e:
                logger.warning(f"Could not parse configuration file at {config_path}: {e}")
        else:
            logger.info("Configuration file not found. Using default embedding generator settings.")

        # 2. Initialize SentenceTransformer
        logger.info(f"Initializing local embedding model '{self.model_name}'...")
        try:
            self.model = SentenceTransformer(self.model_name, device="cpu")
            logger.info(f"Local embedding model '{self.model_name}' loaded successfully.")
        except Exception as e:
            logger.critical(f"Failed to load sentence-transformers model '{self.model_name}': {e}")
            raise RuntimeError(f"Failed to load model '{self.model_name}'") from e

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generates dense vector embeddings for a list of string texts.

        Args:
            texts (List[str]): List of texts to encode.

        Returns:
            np.ndarray: A 2D numpy array of shape (num_texts, embedding_dimension).
        """
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        logger.info(f"Generating embeddings for {len(texts)} texts in batches of {self.batch_size}...")
        try:
            # Generate local embeddings
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            # Ensure float32 representation
            embeddings_np = np.array(embeddings, dtype=np.float32)
            logger.info(f"Generated embeddings shape: {embeddings_np.shape}")
            return embeddings_np
        except Exception as e:
            logger.error(f"Error during embedding generation: {e}")
            raise RuntimeError("Embedding generation failed") from e

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extracts text from a list of chunk dictionaries, generates embeddings,
        and adds the embedding representation as a JSON-serializable list to each chunk.

        Args:
            chunks (List[Dict[str, Any]]): List of chunk dictionaries containing a 'text' key.

        Returns:
            List[Dict[str, Any]]: The list of chunk dictionaries, each enriched with an 'embedding' key.
        """
        if not chunks:
            return []

        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.generate_embeddings(texts)

        # Enrich chunks in-place with list-serialized embeddings for storage compatibility
        for i, chunk in enumerate(chunks):
            chunk["embedding"] = embeddings[i].tolist()

        return chunks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generator = EmbeddingGenerator()
    test_texts = ["Welcome to Google Cloud", "Reliance Retail operates supermarket chains."]
    vectors = generator.generate_embeddings(test_texts)
    print(f"Sample vectors count: {len(vectors)}, dimensions: {vectors.shape[1]}")
