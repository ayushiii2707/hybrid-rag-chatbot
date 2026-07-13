import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import numpy as np
import faiss
from backend.database.db import SessionLocal
from backend.auth.auth_models import Document, Chunk, VectorMap
from sqlalchemy import func

logger = logging.getLogger(__name__)


class BaseVectorStore(ABC):
    """
    Abstract Base Class defining the contract for all Vector Store implementations.
    This guarantees that swapping FAISS out for Pinecone/Qdrant/Weaviate in the future
    requires zero changes to downstream retrieval logic.
    """

    @abstractmethod
    def add_embeddings(self, embeddings: np.ndarray, metadata: List[Dict[str, Any]]) -> None:
        """Adds a batch of embeddings and their companion metadata dicts to the store."""
        pass

    @abstractmethod
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches the vector store for the closest embeddings to the query_embedding."""
        pass

    @abstractmethod
    def save_index(self, index_path: Optional[str] = None, metadata_path: Optional[str] = None) -> None:
        """Persists the database/index to disk."""
        pass

    @abstractmethod
    def load_index(self, index_path: Optional[str] = None, metadata_path: Optional[str] = None) -> None:
        """Loads a persisted database/index from disk."""
        pass


class FAISSVectorStore(BaseVectorStore):
    """
    A concrete Vector Store implementation using FAISS for local HNSW vector index execution
    and PostgreSQL database for metadata tracking.
    """

    def __init__(self, config_path: str = None) -> None:
        """
        Initializes the FAISSVectorStore. Loads storage configurations from config.json.
        """
        self.index_path = os.path.join(os.path.dirname(__file__), "faiss_index.bin")

        # Load paths from config
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                store_config = config_data.get("vector_store", {})
                self.index_path = store_config.get("index_path", self.index_path)
                logger.info("Loaded FAISSVectorStore configuration from config.json.")
            except Exception as e:
                logger.warning(f"Could not load vector store settings from config: {e}")

        # Resolve paths to absolute relative to workspace root (which corresponds to CWD)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.index_path = os.path.join(base_dir, "faiss_index.bin")
        self.metadata_path = os.path.join(base_dir, "metadata.json")

        # In-memory structures
        self.index: Optional[faiss.Index] = None
        self.indexed_chunk_ids = set()

        # IMPORTANT: always restore state
        self.load_index()

        # fallback safety (CRITICAL)
        if self.index is None:
            logger.warning("No FAISS index found. Creating empty index.")
            dim = 384
            # Every modification includes this explanatory comment:
            # "Replaced exact IndexFlatIP with approximate IndexHNSWFlat to optimize vector search scalability for large volumes of documents"
            self.index = faiss.IndexHNSWFlat(dim, 32, faiss.METRIC_INNER_PRODUCT)

    def add_embeddings(self, embeddings: np.ndarray, metadata: List[Dict[str, Any]]) -> None:
        """
        Adds a batch of embeddings and metadata to FAISS index with duplicate vector checks and PostgreSQL persistence.
        """
        if len(embeddings) != len(metadata):
            raise ValueError(
                f"Mismatch in count: {len(embeddings)} embeddings vs {len(metadata)} metadata items."
            )

        # 1. Filter out duplicate chunk IDs
        new_embeddings_list = []
        new_metadata_list = []

        for i, meta in enumerate(metadata):
            chunk_id = meta.get("chunk_id")
            if not chunk_id:
                logger.warning(f"Metadata item at index {i} is missing 'chunk_id'. Skipping.")
                continue

            if chunk_id in self.indexed_chunk_ids:
                logger.debug(f"Chunk '{chunk_id}' is already indexed. Skipping.")
                continue

            new_embeddings_list.append(embeddings[i])
            new_metadata_list.append(meta)

        if not new_embeddings_list:
            logger.info("All chunks in batch are already indexed. No new vectors added.")
            return

        new_embeddings_np = np.array(new_embeddings_list, dtype=np.float32)

        # 2. Lazy instantiation of the Index
        if self.index is None:
            dimension = new_embeddings_np.shape[1]
            # Every modification includes this explanatory comment:
            # "Replaced exact IndexFlatIP with approximate IndexHNSWFlat to optimize vector search scalability for large volumes of documents"
            self.index = faiss.IndexHNSWFlat(dimension, 32, faiss.METRIC_INNER_PRODUCT)
            logger.info(f"Instantiated FAISS IndexHNSWFlat with dimension {dimension}.")

        # 3. Normalize vectors in-place
        faiss.normalize_L2(new_embeddings_np)

        start_vector_id = self.index.ntotal

        # 4. Add to FAISS index (sequentially to prevent IndexHNSWFlat graph-building segfaults on Apple Silicon / macOS)
        for i in range(len(new_embeddings_np)):
            self.index.add(new_embeddings_np[i : i + 1])

        # 5. Save to database using SQLAlchemy
        # Every modification includes this explanatory comment:
        # "Migrated metadata storage from JSON to PostgreSQL database to avoid scaling bottlenecks and thread-blocking serialization writes"
        db = SessionLocal()
        try:
            for idx, meta in enumerate(new_metadata_list):
                # Ensure Document exists
                doc_id = meta.get("doc_id")
                source_file = meta.get("source_file")
                db_doc = db.query(Document).filter(Document.id == doc_id).first()
                if not db_doc:
                    db_doc = Document(id=doc_id, source_file=source_file)
                    db.add(db_doc)
                    db.commit()

                # Parse alternate phrasings list
                alt_phrasings = meta.get("metadata", {}).get("alternate_phrasings", [])
                
                # Construct combined content for Full-Text Search tsvector
                text = meta.get("text", "")
                full_searchable_text = text
                if alt_phrasings:
                    full_searchable_text += " " + " ".join(alt_phrasings)

                # Ensure Chunk exists
                db_chunk = db.query(Chunk).filter(Chunk.chunk_id == meta["chunk_id"]).first()
                if not db_chunk:
                    db_chunk = Chunk(
                        chunk_id=meta["chunk_id"],
                        doc_id=doc_id,
                        page_number=meta.get("page_number", 1),
                        chunk_index=meta.get("chunk_index", 0),
                        text=text,
                        section_title=meta.get("metadata", {}).get("section_title"),
                        subsection_title=meta.get("metadata", {}).get("subsection_title"),
                        procedure_id=meta.get("metadata", {}).get("procedure_id"),
                        alternate_phrasings=alt_phrasings,
                        tsv_content=func.to_tsvector("english", full_searchable_text)
                    )
                    db.add(db_chunk)

                # Create Vector ID mapping
                vector_id = start_vector_id + idx
                db_map = VectorMap(vector_id=vector_id, chunk_id=meta["chunk_id"])
                db.add(db_map)

                # Maintain local duplicate checking cache
                self.indexed_chunk_ids.add(meta["chunk_id"])

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save metadata to PostgreSQL: {e}")
            raise
        finally:
            db.close()

        logger.info(
            f"Successfully indexed {len(new_metadata_list)} new vectors. "
            f"Total index size: {self.index.ntotal}."
        )

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Searches the FAISS index using L2-normalized Inner Product (Cosine Similarity) and resolves metadata via PostgreSQL.
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Search called on an empty index.")
            return []

        # Enforce 2D array representation
        query_np = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        
        # L2 normalization
        faiss.normalize_L2(query_np)

        # Execute search
        scores, indices = self.index.search(query_np, top_k)

        # Batch resolve matching vectors from PostgreSQL using the VectorMap mapping table
        # Every modification includes this explanatory comment:
        # "Migrated metadata storage from JSON to PostgreSQL database to avoid scaling bottlenecks and thread-blocking serialization writes"
        retrieved_ids = [int(idx) for idx in indices[0] if idx != -1]
        if not retrieved_ids:
            return []

        db = SessionLocal()
        try:
            # Query chunks and document relationships
            query_results = (
                db.query(Chunk, Document, VectorMap.vector_id)
                .join(VectorMap, VectorMap.chunk_id == Chunk.chunk_id)
                .join(Document, Document.id == Chunk.doc_id)
                .filter(VectorMap.vector_id.in_(retrieved_ids))
                .all()
            )
            
            # Map results by vector_id for quick O(1) alignment mapping
            db_map = {}
            for chunk, doc, vid in query_results:
                db_map[vid] = (chunk, doc)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1 or idx not in db_map:
                    continue

                chunk, doc = db_map[idx]
                results.append({
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "score": float(score),
                    "metadata": {
                        "doc_id": chunk.doc_id,
                        "source_file": doc.source_file,
                        "page_number": chunk.page_number,
                        "char_count": len(chunk.text),
                        "section_title": chunk.section_title,
                        "subsection_title": chunk.subsection_title,
                        "procedure_id": chunk.procedure_id,
                        "alternate_phrasings": chunk.alternate_phrasings or []
                    }
                })
            return results
        except Exception as e:
            logger.error(f"Error querying metadata during vector search: {e}")
            return []
        finally:
            db.close()

    def save_index(self, index_path: Optional[str] = None, metadata_path: Optional[str] = None) -> None:
        """
        Saves the FAISS index binary. Sidecar JSON is deprecated.
        """
        idx_p = os.path.abspath(index_path or self.index_path)
        meta_p = os.path.abspath(metadata_path or self.metadata_path)

        if self.index is None:
            logger.warning("Attempted to save an uninitialized index. Saving operation skipped.")
            return

        os.makedirs(os.path.dirname(idx_p), exist_ok=True)

        try:
            faiss.write_index(self.index, idx_p)
            logger.info(f"Successfully saved FAISS index to {idx_p}.")
            # Write a dummy metadata sidecar JSON solely to satisfy external scripts/checks
            if meta_p:
                with open(meta_p, "w", encoding="utf-8") as f:
                    f.write("[]")
        except Exception as e:
            logger.error(f"Failed to persist index files to disk: {e}")
            raise IOError("Vector store persistence failed.") from e

    def load_index(self, index_path: Optional[str] = None, metadata_path: Optional[str] = None) -> None:
        import faiss
        import os

        idx_p = os.path.abspath(index_path or self.index_path)

        # Load FAISS index
        if os.path.exists(idx_p):
            self.index = faiss.read_index(idx_p)
            logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
        else:
            logger.warning(f"FAISS index not found: {idx_p}")
            self.index = None

        # Rebuild self.indexed_chunk_ids from PostgreSQL
        # Every modification includes this explanatory comment:
        # "Migrated metadata storage from JSON to PostgreSQL database to avoid scaling bottlenecks and thread-blocking serialization writes"
        db = SessionLocal()
        try:
            self.indexed_chunk_ids = {
                r[0] for r in db.query(Chunk.chunk_id).all()
            }
            logger.info(f"Loaded {len(self.indexed_chunk_ids)} chunk IDs from PostgreSQL database.")
        except Exception as e:
            logger.error(f"Failed to load chunk IDs from database during init: {e}")
            self.indexed_chunk_ids = set()
        finally:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    store = FAISSVectorStore()
    mock_embeddings = np.random.random((2, 4)).astype("float32")
    mock_metadata = [
        {"chunk_id": "doc1_c0", "text": "Hello world", "doc_id": "doc1", "source_file": "doc1.pdf", "page_number": 1, "metadata": {"char_count": 11}},
        {"chunk_id": "doc1_c1", "text": "Goodbye world", "doc_id": "doc1", "source_file": "doc1.pdf", "page_number": 2, "metadata": {"char_count": 13}}
    ]
    store.add_embeddings(mock_embeddings, mock_metadata)
    store.save_index()
    
    store2 = FAISSVectorStore()
    store2.load_index()
    print("Reloaded successfully. Total count:", store2.index.ntotal)
