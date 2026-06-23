import logging
import os
from typing import Dict, Any, List, Optional
from advanced_confidence import AdvancedConfidenceScorer

logger = logging.getLogger(__name__)

class Reranker:
    """
    Reranker coordinates candidate evaluation by combining signals from FAISS vector search 
    and BM25 keyword matching, applying metadata, entity, quality, and ambiguity adjustments.
    """

    def __init__(self, config_path: str = None, spacy_model: str = "en_core_web_sm") -> None:
        """
        Initializes the Reranker with config and loads the AdvancedConfidenceScorer.
        """
        self.scorer = AdvancedConfidenceScorer(config_path=config_path, spacy_model=spacy_model)
        from sentence_transformers import CrossEncoder
        logger.info("Loading Cross-Encoder model: cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        logger.info("Reranker initialized successfully with local Cross-Encoder.")

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        keyword_scores: Dict[str, float],
        original_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Reranks a list of candidate chunks for a query.

        Args:
            query (str): The preprocessed user query.
            candidates (List[Dict[str, Any]]): Retrieved candidate chunk dictionaries containing 'chunk_id', 'text', 'score' (semantic).
            keyword_scores (Dict[str, float]): Normalized BM25 scores for candidate chunk IDs.

        Returns:
            List[Dict[str, Any]]: List of reranked candidates, each augmented with a composite 'score' and 'breakdown' details.
        """
        if not candidates:
            return []

        # Predict semantic match scores in a single batch using local Cross-Encoder
        pairs = [(query, cand.get("text", "")) for cand in candidates]
        logger.info(f"Computing Cross-Encoder predictions for {len(pairs)} candidates...")
        ce_scores = self.cross_encoder.predict(pairs) if pairs else []

        import math
        def sigmoid(x):
            return 1.0 / (1.0 + math.exp(-x))

        scored_candidates = []
        for idx, cand in enumerate(candidates):
            chunk_id = cand["chunk_id"]
            chunk_text = cand.get("text", "")
            faiss_score = cand.get("score", 0.0)  # Raw similarity score from FAISS
            
            # Map Cross-Encoder output logit to [0, 1] probability
            raw_ce_logit = ce_scores[idx] if idx < len(ce_scores) else 0.0
            ce_score = sigmoid(raw_ce_logit)
            
            # Retrieve BM25 keyword score for this chunk
            keyword_score = keyword_scores.get(chunk_id, 0.0)
            
            # Retrieve ranks for retrieval agreement check
            faiss_rank = cand.get("faiss_rank", 999)
            bm25_rank = cand.get("bm25_rank", 999)
            
            agreement_detected = (faiss_rank <= 30) and (bm25_rank <= 30)
            if agreement_detected:
                # Compute decaying boost based on rank proximity (max boost = 0.03)
                factor_faiss = 1.0 - ((faiss_rank - 1) / 30.0)
                factor_bm25 = 1.0 - ((bm25_rank - 1) / 30.0)
                factor_faiss = max(0.0, min(1.0, factor_faiss))
                factor_bm25 = max(0.0, min(1.0, factor_bm25))
                agreement_boost = round(0.03 * factor_faiss * factor_bm25, 4)
            else:
                agreement_boost = 0.0

            # Developer Logging
            logger.info(
                f"[RetrievalAgreement] Candidate ID: {chunk_id} | "
                f"Semantic Rank: {faiss_rank} | "
                f"BM25 Rank: {bm25_rank} | "
                f"Agreement Detected: {agreement_detected} | "
                f"Agreement Boost Applied: {agreement_boost:.4f}"
            )

            # Calculate source agreement metrics for this candidate against all candidate chunks
            meta = cand.get("metadata", {})
            proc_id = meta.get("procedure_id")
            sec_title = meta.get("section_title")
            
            supporting_list = []
            for other in candidates:
                if other["chunk_id"] == chunk_id:
                    supporting_list.append(other)
                    continue
                
                other_meta = other.get("metadata", {})
                other_proc = other_meta.get("procedure_id")
                other_sec = other_meta.get("section_title")
                
                matches = False
                if proc_id and other_proc == proc_id:
                    matches = True
                elif sec_title and other_sec == sec_title:
                    matches = True
                
                if matches:
                    supporting_list.append(other)
            
            supporting_chunks = len(supporting_list)
            supporting_documents = len(set(other.get("metadata", {}).get("source_file") for other in supporting_list if other.get("metadata", {}).get("source_file")))
            
            source_agreement_detected = (supporting_chunks >= 2)
            if source_agreement_detected:
                raw_source_boost = 0.005 * supporting_chunks + 0.005 * supporting_documents - 0.01
                source_agreement_boost = round(min(0.03, max(0.0, raw_source_boost)), 4)
            else:
                source_agreement_boost = 0.0

            # Developer Logging
            logger.info(
                f"[SourceAgreement] Candidate ID: {chunk_id} | "
                f"Supporting Chunks: {supporting_chunks} | "
                f"Supporting Documents: {supporting_documents} | "
                f"Source Agreement Detected: {source_agreement_detected} | "
                f"Source Agreement Boost Applied: {source_agreement_boost:.4f}"
            )

            # Score the candidate using our advanced confidence formulas, passing cross-encoder score as semantic_score, retrieval agreement boost, and source agreement boost
            score_details = self.scorer.score_candidate(
                query=original_query if original_query is not None else query,
                chunk_text=chunk_text,
                semantic_score=ce_score,
                keyword_score=keyword_score,
                chunk_metadata=cand.get("metadata", {}),
                agreement_boost=agreement_boost,
                agreement_detected=agreement_detected,
                faiss_rank=faiss_rank,
                bm25_rank=bm25_rank,
                source_agreement_boost=source_agreement_boost,
                source_agreement_detected=source_agreement_detected,
                supporting_chunks=supporting_chunks,
                supporting_documents=supporting_documents
            )

            # Log after advanced confidence calculation (stage AFTER_ADVANCED_CONFIDENCE)
            logger.info(
                f"STAGE: AFTER_ADVANCED_CONFIDENCE | chunk_id={chunk_id} | confidence_score={score_details['score']}"
            )

            # Build rich scored chunk dictionary
            scored_cand = dict(cand)
            scored_cand["score"] = score_details["score"]
            scored_cand["breakdown"] = score_details["breakdown"]
            scored_cand["breakdown"]["faiss_similarity"] = faiss_score
            scored_cand["breakdown"]["cross_encoder_score"] = ce_score
            scored_cand["breakdown"]["cross_encoder_logit"] = float(raw_ce_logit)
            scored_cand["raw_similarity"] = faiss_score  # Keep track of raw FAISS similarity score
            
            bd = score_details["breakdown"]
            logger.info(
                f"Candidate {chunk_id}: FAISS={faiss_score:.4f} CE={ce_score:.4f} (logit={raw_ce_logit:.4f}) "
                f"BM25={keyword_score:.4f} AnswerType={bd.get('answer_type', 0.0):.3f} "
                f"Answerability={bd.get('answerability', 0.0):.3f} "
                f"Alignment={bd.get('alignment', 0.0):.3f} "
                f"Sufficiency={bd.get('sufficiency', 0.0):.3f} "
                f"→ Composite={score_details['score']:.4f}"
            )

            scored_candidates.append(scored_cand)

        # Sort candidates descending by their composite confidence score
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Apply ambiguity adjustments across candidates (specifically top 2 similarity comparison)
        final_ranked = self.scorer.apply_ambiguity_penalties(scored_candidates)
        
        # Sort again in case scores changed due to penalties (e.g. ambiguity penalties)
        final_ranked.sort(key=lambda x: x["score"], reverse=True)

        logger.info(f"Reranking complete. Top candidate ID: {final_ranked[0]['chunk_id']} (Score: {final_ranked[0]['score']:.4f})")
        return final_ranked
