import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class KeywordRanker:
    """
    A performant keyword ranker delegating to PostgreSQL Full-Text Search.
    Eliminates memory overhead and startup latency of native Python BM25 indexes.
    """

    def __init__(self, metadata_path: str = None, k1: float = 1.5, b: float = 0.75) -> None:
        """
        Initializes the KeywordRanker.
        """
        # Maintain public API compatibility, but index nothing in memory
        self.chunks: List[Dict[str, Any]] = []
        logger.info("KeywordRanker initialized using PostgreSQL Full-Text Search backend.")

    def score_query(self, query: str, candidate_chunk_ids: List[str]) -> Dict[str, float]:
        """
        Scores a list of candidate chunk IDs against a query using PostgreSQL Full-Text Search.
        Returns a dictionary mapping chunk_id to its normalized score [0.0, 1.0].
        """
        if not candidate_chunk_ids or not query.strip():
            return {cid: 0.0 for cid in candidate_chunk_ids}

        # Initialize scores to 0.0 for all candidates
        scores = {cid: 0.0 for cid in candidate_chunk_ids}

        import re
        words = re.findall(r'\b\w+\b', query)
        if not words:
            return scores

        # Build: plainto_tsquery('english', :w0) || plainto_tsquery('english', :w1) ...
        query_parts = [f"plainto_tsquery('english', :w{i})" for i, _ in enumerate(words)]
        tsquery_sql = " || ".join(query_parts)

        # Every modification includes this explanatory comment:
        # "Replaced the local in-memory BM25 ranker with PostgreSQL Full-Text Search ts_rank_cd to avoid RAM bloat and startup overhead"
        from sqlalchemy import text
        from backend.database.db import SessionLocal
        
        db = SessionLocal()
        try:
            sql = text(
                f"SELECT chunk_id, ts_rank_cd(tsv_content, {tsquery_sql}) as rank "
                "FROM chunks "
                "WHERE chunk_id = ANY(:candidate_ids)"
            )
            params = {f"w{i}": w for i, w in enumerate(words)}
            params["candidate_ids"] = candidate_chunk_ids
            
            results = db.execute(sql, params).all()
            
            raw_scores = {}
            for chunk_id, rank in results:
                raw_scores[chunk_id] = float(rank or 0.0)

            # Max-normalize scores
            max_score = max(raw_scores.values()) if raw_scores else 0.0
            if max_score > 0.0:
                for chunk_id, rank in raw_scores.items():
                    if chunk_id in scores:
                        scores[chunk_id] = rank / max_score
        except Exception as e:
            logger.error(f"Failed to score query using PostgreSQL FTS: {e}")
        finally:
            db.close()

        return scores
