import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Bootstrap path to allow importing from backend/embeddings
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))

from retrieval_engine import RetrievalEngine
from keyword_ranker import KeywordRanker
from reranker import Reranker

logger = logging.getLogger(__name__)


class HybridRetriever(RetrievalEngine):
    """
    Hybrid Retriever that extends RetrievalEngine.
    Retrieves candidates from FAISS vector store, expands them dynamically to collect
    procedural neighbors/context, scores them using the KeywordRanker (BM25),
    and reranks them to yield a composite-scored list of documents.
    """

    def __init__(
        self,
        config_path: str = None,
        spacy_model: str = "en_core_web_sm",
        metadata_path: str = None
    ) -> None:
        """
        Initializes the HybridRetriever.
        """
        emb_config_path = os.path.join(BACKEND_DIR, "embeddings", "config.json")
        super().__init__(config_path=emb_config_path)

        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")

        self.keyword_ranker = KeywordRanker(metadata_path=metadata_path)
        self.reranker = Reranker(config_path=config_path, spacy_model=spacy_model)
        
        self.candidate_pool_size = 12
        
        # Build lookup mapping for fast corpus O(1) searches
        self.chunks_by_id = {c["chunk_id"]: c for c in self.keyword_ranker.chunks}
        logger.info("HybridRetriever initialized successfully with metadata mapping.")

    def _is_procedural_query(self, query: str) -> bool:
        """Helper to check if query seeks workflow instructions."""
        procedural_keywords = ["how to", "step", "procedure", "process", "instruction", "guide", "workflow", "stage", "phase", "add", "check", "register", "status"]
        query_lower = query.lower()
        return any(kw in query_lower for kw in procedural_keywords)

    def retrieve_best_chunk(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Standard single-chunk retrieval mode.
        """
        candidates = super().retrieve(
            query=query,
            top_k=self.candidate_pool_size,
            threshold=0.15
        )
        if not candidates:
            return []

        # Map full metadata properties back to candidates
        for cand in candidates:
            chunk_obj = self.chunks_by_id.get(cand["chunk_id"])
            if chunk_obj:
                cand["metadata"].update(chunk_obj.get("metadata", {}))

        candidate_ids = [cand["chunk_id"] for cand in candidates]
        keyword_scores = self.keyword_ranker.score_query(query, candidate_ids)

        reranked_candidates = self.reranker.rerank(
            query=query,
            candidates=candidates,
            keyword_scores=keyword_scores
        )

        result_top_k = top_k if top_k is not None else self.top_k
        return reranked_candidates[:result_top_k]

    def retrieve_candidate_chunks(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Procedural candidate expansion mode. Gathers neighboring, same-section,
        and same-procedure chunks to ensure workflow continuity.
        """
        base_candidates = super().retrieve(
            query=query,
            top_k=self.candidate_pool_size,
            threshold=0.15
        )
        if not base_candidates:
            return []

        # Enrich initial semantic candidates
        for cand in base_candidates:
            chunk_obj = self.chunks_by_id.get(cand["chunk_id"])
            if chunk_obj:
                cand["metadata"].update(chunk_obj.get("metadata", {}))

        # Perform candidate expansion based on metadata adjacency
        expanded_cands_dict = {cand["chunk_id"]: cand for cand in base_candidates}

        for cand in base_candidates:
            chunk_id = cand["chunk_id"]
            parent_score = cand["score"]
            chunk_obj = self.chunks_by_id.get(chunk_id)
            if not chunk_obj:
                continue

            doc_id = chunk_obj.get("doc_id")
            source_file = chunk_obj.get("source_file")
            chunk_index = chunk_obj.get("chunk_index")
            meta = chunk_obj.get("metadata", {})
            sec_title = meta.get("section_title")
            proc_id = meta.get("procedure_id")

            # Look for matching neighbors in the entire corpus
            for corpus_chunk in self.keyword_ranker.chunks:
                corp_id = corpus_chunk["chunk_id"]
                if corp_id in expanded_cands_dict:
                    continue

                if corpus_chunk.get("doc_id") != doc_id:
                    continue

                corp_index = corpus_chunk.get("chunk_index")
                corp_meta = corpus_chunk.get("metadata", {})
                corp_sec = corp_meta.get("section_title")
                corp_proc = corp_meta.get("procedure_id")

                is_neighbor = False
                is_same_section = False
                is_same_proc = False

                # Neighboring chunks (previous and next indices)
                if corp_index is not None and chunk_index is not None:
                    if abs(corp_index - chunk_index) == 1:
                        is_neighbor = True

                # Same-section chunks
                if sec_title and corp_sec == sec_title:
                    is_same_section = True

                # Same-procedure chunks
                if proc_id and corp_proc == proc_id:
                    is_same_proc = True

                if is_neighbor or is_same_section or is_same_proc:
                    # Assign discounted score
                    discount = 0.95 if is_neighbor else 0.90
                    score = parent_score * discount

                    expanded_cand = {
                        "chunk_id": corp_id,
                        "text": corpus_chunk.get("text", ""),
                        "score": score,
                        "metadata": {
                            "doc_id": doc_id,
                            "source_file": source_file,
                            "page_number": corpus_chunk.get("page_number"),
                            "char_count": corp_meta.get("char_count", len(corpus_chunk.get("text", "")))
                        }
                    }
                    expanded_cand["metadata"].update(corp_meta)
                    expanded_cands_dict[corp_id] = expanded_cand

        expanded_candidates = list(expanded_cands_dict.values())

        # BM25 Keyword scoring
        candidate_ids = [c["chunk_id"] for c in expanded_candidates]
        keyword_scores = self.keyword_ranker.score_query(query, candidate_ids)

        # Composite Reranking
        reranked_candidates = self.reranker.rerank(
            query=query,
            candidates=expanded_candidates,
            keyword_scores=keyword_scores
        )

        result_top_k = top_k if top_k is not None else self.top_k
        return reranked_candidates[:result_top_k]

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves, reranks, and filters document chunks using both semantic and keyword signals.
        Dynamically adapts between Best-Chunk retrieval and Candidate Expansion.
        """
        if not query or not query.strip():
            return []

        if self._is_procedural_query(query):
            logger.info("Procedural query detected. Running Candidate Expansion mode.")
            results = self.retrieve_candidate_chunks(query, top_k=top_k, threshold=threshold)
        else:
            logger.info("Factual/Standard query detected. Running Best-Chunk mode.")
            results = self.retrieve_best_chunk(query, top_k=top_k, threshold=threshold)

        logger.info(f"HybridRetriever returned {len(results)} matches for query: '{query}'")
        return results
