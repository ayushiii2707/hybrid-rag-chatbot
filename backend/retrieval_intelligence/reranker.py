import logging
import os
from typing import Dict, Any, List
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
        keyword_scores: Dict[str, float]
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

            # Score the candidate using our advanced confidence formulas, passing cross-encoder score as semantic_score
            score_details = self.scorer.score_candidate(
                query=query,
                chunk_text=chunk_text,
                semantic_score=ce_score,
                keyword_score=keyword_score,
                chunk_metadata=cand.get("metadata", {})
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
