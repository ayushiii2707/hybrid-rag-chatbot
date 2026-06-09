import os
import sys

# Bootstrap Paths
BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "query_engine"))
sys.path.insert(0, os.path.join(BACKEND_DIR, "retrieval_intelligence"))

from hybrid_retriever import HybridRetriever
from query_preprocessor import QueryPreprocessor

preprocessor = QueryPreprocessor()
query = "how to input micr code in bank details"
res = preprocessor.preprocess_query(query)
expanded_query = preprocessor.expand_synonyms(res["corrected_query"])

print("Query:", expanded_query)
retriever = HybridRetriever()

# Step 1: retrieve base candidates from FAISS
base_candidates = super(HybridRetriever, retriever).retrieve(expanded_query, top_k=30)
print(f"\n--- Base FAISS Candidates ({len(base_candidates)}) ---")
target_id = "3b97da58a590c41e2833e6360925ec9dc0349b82e177e1dadba8fbd85a089d57_c28"
for idx, c in enumerate(base_candidates):
    if c["chunk_id"] == target_id:
        print(f"Target found in Base candidates at rank {idx+1} with FAISS score {c['score']:.4f}")
    if idx < 5:
        print(f" Rank {idx+1}: {c['chunk_id']} | FAISS Score: {c['score']:.4f}")

# Step 2: candidate expansion
expanded_cands_dict = {cand["chunk_id"]: cand for cand in base_candidates}
for cand in base_candidates:
    chunk_id = cand["chunk_id"]
    parent_score = cand["score"]
    chunk_obj = retriever.chunks_by_id.get(chunk_id)
    if not chunk_obj:
        continue
    doc_id = chunk_obj.get("doc_id")
    source_file = chunk_obj.get("source_file")
    chunk_index = chunk_obj.get("chunk_index")
    meta = chunk_obj.get("metadata", {})
    sec_title = meta.get("section_title")
    proc_id = meta.get("procedure_id")

    for corpus_chunk in retriever.keyword_ranker.chunks:
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

        if corp_index is not None and chunk_index is not None:
            if abs(corp_index - chunk_index) == 1:
                is_neighbor = True
        if sec_title and corp_sec == sec_title:
            is_same_section = True
        if proc_id and corp_proc == proc_id:
            is_same_proc = True

        if is_neighbor or is_same_section or is_same_proc:
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
unique_expanded_dict = {}
for cand in expanded_candidates:
    unique_expanded_dict[cand["chunk_id"]] = cand
deduped_expanded = list(unique_expanded_dict.values())

print(f"\n--- Expanded Candidates ({len(deduped_expanded)}) ---")
if target_id in unique_expanded_dict:
    print(f"Target is present in expanded candidates! Score: {unique_expanded_dict[target_id]['score']:.4f}")
else:
    print("Target is NOT present in expanded candidates!")

# Step 3: BM25 Scoring
candidate_ids = [c["chunk_id"] for c in deduped_expanded]
keyword_scores = retriever.keyword_ranker.score_query(expanded_query, candidate_ids)
print("\n--- BM25 Keyword Scores ---")
if target_id in keyword_scores:
    print(f"Target BM25 Score: {keyword_scores[target_id]:.4f}")
else:
    print("Target has no BM25 Score.")

# Step 4: Reranking
retriever._enrich_agreement_ranks(expanded_query, deduped_expanded, base_candidates)
reranked_candidates = retriever.reranker.rerank(
    query=expanded_query,
    candidates=deduped_expanded,
    keyword_scores=keyword_scores
)

print(f"\n--- Reranked Candidates ({len(reranked_candidates)}) ---")
for idx, c in enumerate(reranked_candidates):
    if c["chunk_id"] == target_id:
        print(f"Target found in reranked candidates at rank {idx+1} with final composite score {c['score']:.4f}")
        print("  Breakdown:", c["breakdown"])
    if idx < 5:
        print(f" Rank {idx+1}: {c['chunk_id']} | Final Score: {c['score']:.4f} | source_file: {c['metadata']['source_file']}")
