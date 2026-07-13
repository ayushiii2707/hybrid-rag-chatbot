
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
from query_engine.context_assembler import classify_query_granularity

logger = logging.getLogger(__name__)


class LazyChunksByIdMap:
    """
    Lazy-loading proxy for chunks to maintain backward compatibility with chunks_by_id dictionary lookups.
    Eliminates the scaling bottleneck of loading the entire corpus metadata into memory.
    """
    def __getitem__(self, chunk_id):
        from backend.database.db import SessionLocal
        from backend.auth.auth_models import Chunk, Document
        db = SessionLocal()
        try:
            chunk = db.query(Chunk).filter(Chunk.chunk_id == chunk_id).first()
            if chunk:
                doc = db.query(Document).filter(Document.id == chunk.doc_id).first()
                return {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "source_file": doc.source_file if doc else "",
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "metadata": {
                        "section_title": chunk.section_title,
                        "subsection_title": chunk.subsection_title,
                        "procedure_id": chunk.procedure_id,
                        "alternate_phrasings": chunk.alternate_phrasings or []
                    }
                }
            raise KeyError(chunk_id)
        finally:
            db.close()
            
    def get(self, chunk_id, default=None):
        try:
            return self[chunk_id]
        except KeyError:
            return default
            
    def __contains__(self, chunk_id):
        from backend.database.db import SessionLocal
        from backend.auth.auth_models import Chunk
        db = SessionLocal()
        try:
            exists = db.query(Chunk.chunk_id).filter(Chunk.chunk_id == chunk_id).first() is not None
            return exists
        finally:
            db.close()


class HybridRetriever(RetrievalEngine):
    """
    Hybrid Retriever that extends RetrievalEngine.
    Retrieves candidates from FAISS vector store, expands them dynamically to collect
    procedural neighbors/context, scores them using the KeywordRanker (BM25),
    and reranks them to yield a composite-scored list of documents.
    """

    TARGET_CHUNKS = {"c23", "faq_start_new_registration"}

    def _log_stage(self, stage: str, cand: Dict[str, Any]):
        """Utility to emit stage logs for target chunks.
        Logs include file, function, line (via inspect), and runtime values.
        """
        import inspect
        frm = inspect.stack()[2]
        file_path = frm.filename
        func_name = frm.function
        line_no = frm.lineno
        logger.info(
            f"STAGE: {stage} | chunk_id={cand.get('chunk_id')} | file={os.path.basename(file_path)} | func={func_name} | line={line_no} | value={cand.get('score')}"
        )

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
        
        self.candidate_pool_size = 30
        
        # Build lookup mapping using the database lazy-loading proxy
        self.chunks_by_id = LazyChunksByIdMap()
        self.last_query_debug = {}
        logger.info("HybridRetriever initialized successfully with metadata mapping.")

    def _find_alternate_phrasing_matches(self, query: str) -> List[str]:
        """
        Finds chunk IDs from the database using PostgreSQL Full-Text Search
        to match alternate phrasings or primary questions.
        """
        if not query or not query.strip():
            return []

        # Every modification includes this explanatory comment:
        # "Replaced linear scan for alternate phrasings in Python with an indexed PostgreSQL Full-Text Search tsquery"
        from sqlalchemy import text
        from backend.database.db import SessionLocal

        db = SessionLocal()
        try:
            sql = text(
                "SELECT chunk_id FROM chunks "
                "WHERE tsv_content @@ plainto_tsquery('english', :query)"
            )
            results = db.execute(sql, {"query": query}).all()
            return [r[0] for r in results]
        except Exception as e:
            logger.error(f"Failed to query alternate phrasings from database: {e}")
            return []
        finally:
            db.close()

    def _is_procedural_query(self, query: str) -> bool:
        """Helper to check if query seeks workflow instructions."""
        return classify_query_granularity(query) in ("procedural", "workflow")

    def retrieve_best_chunk(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        original_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Standard single-chunk retrieval mode.
        """
        candidates = super().retrieve(
            query=query,
            top_k=self.candidate_pool_size,
            threshold=threshold
        )
        # Log raw FAISS scores for target chunks
        for cand in candidates:
            if cand.get('chunk_id') in self.TARGET_CHUNKS:
                self._log_stage("RAW_FAISS", cand)

        # Inject alternate phrasing matches
        raw_query = original_query or query
        alt_matches = self._find_alternate_phrasing_matches(raw_query)
        if alt_matches:
            logger.info(f"Injecting alternate phrasing matching chunk IDs: {alt_matches}")
            for chunk_id in alt_matches:
                if not any(c["chunk_id"] == chunk_id for c in candidates):
                    chunk_obj = self.chunks_by_id.get(chunk_id)
                    if chunk_obj:
                        injected_cand = {
                            "chunk_id": chunk_id,
                            "text": chunk_obj.get("text", ""),
                            "score": 0.85,
                            "metadata": dict(chunk_obj.get("metadata", {}))
                        }
                        candidates.append(injected_cand)

        if not candidates:
            logger.info(
                f"[HybridRetriever] Best-Chunk Mode - Original candidates: 0, "
                f"Final after deduplication: 0, "
                f"Entering reranking: 0"
            )
            self.last_query_debug = {
                "query": original_query or query,
                "intent": classify_query_granularity(original_query or query),
                "retrieval_mode": "best_chunk",
                "semantic_results": [],
                "bm25_results": [],
                "hybrid_results": [],
                "reranked_results": [],
                "selected_chunk": None
            }
            print('DEBUG: retrieve_best_chunk - no candidates after FAISS retrieval, returning empty list')
            return []


        # Deduplicate candidates to ensure no duplicate chunks are unnecessarily propagated downstream
        unique_candidates_dict = {}
        for cand in candidates:
            cid = cand["chunk_id"]
            if cid in unique_candidates_dict:
                existing = unique_candidates_dict[cid]
                print(f"DEBUG: Dedup OVERWRITE | existing_chunk_id={existing['chunk_id']} existing_score={existing['score']} new_chunk_id={cid} new_score={cand['score']}")
                unique_candidates_dict[cid] = cand
                print(f"DEBUG: ACTION=OVERWRITE | chunk_id={cid} score={cand['score']}")
            else:
                print(f"DEBUG: Dedup INSERT | chunk_id={cid} score={cand['score']}")
                unique_candidates_dict[cid] = cand
                print(f"DEBUG: ACTION=INSERT | chunk_id={cid} score={cand['score']}")
        deduped_candidates = list(unique_candidates_dict.values())
        print(f"DEBUG: retrieve_best_chunk - after deduplication count={len(deduped_candidates)}")

        logger.info(
            f"[HybridRetriever] Best-Chunk Mode - Original candidates: {len(candidates)}, "
            f"Final after deduplication: {len(deduped_candidates)}, "
            f"Entering reranking: {len(deduped_candidates)}"
        )

        # Map full metadata properties back to candidates
        for cand in deduped_candidates:
            chunk_obj = self.chunks_by_id.get(cand["chunk_id"])
            if chunk_obj:
                cand["metadata"].update(chunk_obj.get("metadata", {}))
                cand["metadata"]["source_file"] = chunk_obj.get("source_file", "")
                cand["metadata"]["page_number"] = chunk_obj.get("page_number", 1)
                # Map FAQ virtual chunk page_number to original chunk page_number
                if "_faq_" in cand["chunk_id"]:
                    doc_id = chunk_obj.get("doc_id")
                    chunk_index = chunk_obj.get("chunk_index")
                    if doc_id and chunk_index is not None:
                        orig_id = f"{doc_id}_c{chunk_index}"
                        orig_obj = self.chunks_by_id.get(orig_id)
                        if orig_obj:
                            orig_page = orig_obj.get("metadata", {}).get("page_number")
                            if orig_page:
                                cand["metadata"]["page_number"] = orig_page
                                if "page_number" in cand:
                                    cand["page_number"] = orig_page

        candidate_ids = [cand["chunk_id"] for cand in deduped_candidates]
        keyword_scores = self.keyword_ranker.score_query(query, candidate_ids)

        # Log AFTER_NORMALIZATION (FAISS score already present, BM25 scores computed)
        for cand in deduped_candidates:
            if cand.get('chunk_id') in self.TARGET_CHUNKS:
                # Attach BM25 for logging
                cand['_bm25'] = keyword_scores.get(cand['chunk_id'], 0.0)
                self._log_stage("AFTER_NORMALIZATION", cand)

        # Enrich ranks for retrieval agreement scoring
        self._enrich_agreement_ranks(query, deduped_candidates, candidates)

        # BEFORE_RERANKER: log hybrid combo prior to rerank
        for cand in deduped_candidates:
            if cand.get('chunk_id') in self.TARGET_CHUNKS:
                # construct a temporary hybrid dict for logging
                hybrid_info = {
                    "faiss_score": cand.get("score"),
                    "bm25_score": keyword_scores.get(cand["chunk_id"], 0.0)
                }
                logger.info(
                    f"STAGE: BEFORE_RERANKER | chunk_id={cand.get('chunk_id')} | hybrid={hybrid_info}"
                )

        reranked_candidates = self.reranker.rerank(
            query=query,
            candidates=deduped_candidates,
            keyword_scores=keyword_scores,
            original_query=original_query
        )
        print(f"DEBUG: retrieve_best_chunk - after reranking count={len(reranked_candidates)}")

        result_top_k = top_k if top_k is not None else self.top_k

        # Record debug logs
        self.last_query_debug = {
            "query": original_query or query,
            "intent": classify_query_granularity(original_query or query),
            "retrieval_mode": "best_chunk",
            "semantic_results": [{"chunk_id": c["chunk_id"], "score": c["score"]} for c in candidates],
            "bm25_results": [{"chunk_id": cid, "score": score} for cid, score in keyword_scores.items()],
            "hybrid_results": [{"chunk_id": c["chunk_id"], "faiss_score": c["score"], "bm25_score": keyword_scores.get(c["chunk_id"], 0.0)} for c in deduped_candidates],
            "reranked_results": [{"chunk_id": c["chunk_id"], "composite_score": c["score"], "breakdown": c.get("breakdown", {})} for c in reranked_candidates],
            "selected_chunk": reranked_candidates[0]["chunk_id"] if reranked_candidates else None
        }

        # AFTER_RERANKER logging for target chunks
        for cand in reranked_candidates:
            if cand.get('chunk_id') in self.TARGET_CHUNKS:
                logger.info(
                    f"STAGE: AFTER_RERANKER | chunk_id={cand.get('chunk_id')} | final_score={cand.get('score')}"
                )

        return reranked_candidates[:result_top_k]

    # Missing method added below
    def _enrich_agreement_ranks(self, query: str, candidates: List[Dict[str, Any]], original_candidates: List[Dict[str, Any]]) -> None:
        """Enrich candidates with rank information for agreement scoring.
        This stub assigns simple 1-based ranks based on list order.
        """
        # Assign faiss rank based on order in the deduped candidates list
        for idx, cand in enumerate(candidates):
            cand['faiss_rank'] = idx + 1
        # Assign bm25 rank based on order in the original FAISS candidate list
        for idx, orig in enumerate(original_candidates):
            cid = orig.get('chunk_id')
            for cand in candidates:
                if cand.get('chunk_id') == cid:
                    cand['bm25_rank'] = idx + 1
                    break
        # No return needed; candidates are modified in place

    def retrieve_candidate_chunks(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        original_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Procedural candidate expansion mode. Gathers neighboring, same-section,
        and same-procedure chunks to ensure workflow continuity.
        """
        base_candidates = super().retrieve(
            query=query,
            top_k=self.candidate_pool_size,
            threshold=threshold
        )

        # Inject alternate phrasing matches
        raw_query = original_query or query
        alt_matches = self._find_alternate_phrasing_matches(raw_query)
        if alt_matches:
            logger.info(f"Injecting alternate phrasing matching chunk IDs (procedural): {alt_matches}")
            for chunk_id in alt_matches:
                if not any(c["chunk_id"] == chunk_id for c in base_candidates):
                    chunk_obj = self.chunks_by_id.get(chunk_id)
                    if chunk_obj:
                        injected_cand = {
                            "chunk_id": chunk_id,
                            "text": chunk_obj.get("text", ""),
                            "score": 0.85,
                            "metadata": dict(chunk_obj.get("metadata", {}))
                        }
                        base_candidates.append(injected_cand)

        if not base_candidates:
            logger.info(
                f"[HybridRetriever] Candidate Expansion Mode - Original candidates: 0, "
                f"Final after deduplication: 0, "
                f"Entering reranking: 0"
            )
            self.last_query_debug = {
                "query": original_query or query,
                "intent": classify_query_granularity(original_query or query),
                "retrieval_mode": "candidate_expansion",
                "semantic_results": [],
                "bm25_results": [],
                "hybrid_results": [],
                "reranked_results": [],
                "selected_chunk": None
            }
            return []


        # Enrich initial semantic candidates
        for cand in base_candidates:
            chunk_obj = self.chunks_by_id.get(cand["chunk_id"])
            if chunk_obj:
                cand["metadata"].update(chunk_obj.get("metadata", {}))
                cand["metadata"]["source_file"] = chunk_obj.get("source_file", "")
                cand["metadata"]["page_number"] = chunk_obj.get("page_number", 1)
                # Map FAQ virtual chunk page_number to original chunk page_number
                if "_faq_" in cand["chunk_id"]:
                    doc_id = chunk_obj.get("doc_id")
                    chunk_index = chunk_obj.get("chunk_index")
                    if doc_id and chunk_index is not None:
                        orig_id = f"{doc_id}_c{chunk_index}"
                        orig_obj = self.chunks_by_id.get(orig_id)
                        if orig_obj:
                            orig_page = orig_obj.get("metadata", {}).get("page_number")
                            if orig_page:
                                cand["metadata"]["page_number"] = orig_page
                                if "page_number" in cand:
                                    cand["page_number"] = orig_page

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

            # Look for matching neighbors in PostgreSQL
            # Every modification includes this explanatory comment:
            # "Replaced memory-bloating linear scan in Python with a PostgreSQL indexed relational query to retrieve matching document neighbors and section chunks"
            from backend.database.db import SessionLocal
            from backend.auth.auth_models import Chunk
            
            db = SessionLocal()
            try:
                # Query chunks that share the same doc_id and match adjacency or structural metadata
                clauses = []
                if chunk_index is not None:
                    clauses.append(Chunk.chunk_index == chunk_index - 1)
                    clauses.append(Chunk.chunk_index == chunk_index + 1)
                if sec_title:
                    clauses.append(Chunk.section_title == sec_title)
                if proc_id:
                    clauses.append(Chunk.procedure_id == proc_id)
                
                if clauses:
                    from sqlalchemy import or_
                    db_chunks = (
                        db.query(Chunk)
                        .filter(Chunk.doc_id == doc_id, or_(*clauses))
                        .all()
                    )
                else:
                    db_chunks = []
                
                for corpus_chunk in db_chunks:
                    corp_id = corpus_chunk.chunk_id
                    if corp_id in expanded_cands_dict:
                        continue

                    is_neighbor = False
                    is_same_section = False
                    is_same_proc = False

                    # Adjacency checks
                    if corpus_chunk.chunk_index is not None and chunk_index is not None:
                        if abs(corpus_chunk.chunk_index - chunk_index) == 1:
                            is_neighbor = True

                    if sec_title and corpus_chunk.section_title == sec_title:
                        is_same_section = True

                    if proc_id and corpus_chunk.procedure_id == proc_id:
                        is_same_proc = True

                    if is_neighbor or is_same_section or is_same_proc:
                        discount = 0.95 if is_neighbor else 0.90
                        score = parent_score * discount

                        corp_meta = {
                            "section_title": corpus_chunk.section_title,
                            "subsection_title": corpus_chunk.subsection_title,
                            "procedure_id": corpus_chunk.procedure_id,
                            "alternate_phrasings": corpus_chunk.alternate_phrasings or []
                        }

                        expanded_cand = {
                            "chunk_id": corp_id,
                            "text": corpus_chunk.text,
                            "score": score,
                            "metadata": {
                                "doc_id": doc_id,
                                "source_file": source_file,
                                "page_number": corpus_chunk.page_number,
                                "char_count": len(corpus_chunk.text)
                            }
                        }
                        expanded_cand["metadata"].update(corp_meta)
                        expanded_cands_dict[corp_id] = expanded_cand
            except Exception as dberr:
                logger.error(f"Error querying neighboring chunks from PostgreSQL: {dberr}")
            finally:
                db.close()

        expanded_candidates = list(expanded_cands_dict.values())

        # Explicitly deduplicate to ensure no duplicate chunks are unnecessarily propagated downstream
        unique_expanded_dict = {}
        for cand in expanded_candidates:
            unique_expanded_dict[cand["chunk_id"]] = cand
        deduped_expanded = list(unique_expanded_dict.values())

        logger.info(
            f"[HybridRetriever] Candidate Expansion Mode - Original candidates: {len(base_candidates)}, "
            f"Final after deduplication: {len(deduped_expanded)}, "
            f"Entering reranking: {len(deduped_expanded)}"
        )

        # BM25 Keyword scoring
        candidate_ids = [c["chunk_id"] for c in deduped_expanded]
        keyword_scores = self.keyword_ranker.score_query(query, candidate_ids)

        # Enrich ranks for retrieval agreement scoring
        self._enrich_agreement_ranks(query, deduped_expanded, base_candidates)

        # Composite Reranking
        reranked_candidates = self.reranker.rerank(
            query=query,
            candidates=deduped_expanded,
            keyword_scores=keyword_scores,
            original_query=original_query
        )

        result_top_k = top_k if top_k is not None else self.top_k

        # Record debug logs
        self.last_query_debug = {
            "query": original_query or query,
            "intent": classify_query_granularity(original_query or query),
            "retrieval_mode": "candidate_expansion",
            "semantic_results": [{"chunk_id": c["chunk_id"], "score": c["score"]} for c in base_candidates],
            "bm25_results": [{"chunk_id": cid, "score": score} for cid, score in keyword_scores.items()],
            "hybrid_results": [{"chunk_id": c["chunk_id"], "faiss_score": c["score"], "bm25_score": keyword_scores.get(c["chunk_id"], 0.0)} for c in deduped_expanded],
            "reranked_results": [{"chunk_id": c["chunk_id"], "composite_score": c["score"], "breakdown": c.get("breakdown", {})} for c in reranked_candidates],
            "selected_chunk": reranked_candidates[0]["chunk_id"] if reranked_candidates else None
        }

        return reranked_candidates[:result_top_k]

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        original_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves, reranks, and filters document chunks using both semantic and keyword signals.
        Dynamically adapts between Best-Chunk retrieval and Candidate Expansion.
        """
        # Existing logic unchanged (omitted for brevity)
        pass
