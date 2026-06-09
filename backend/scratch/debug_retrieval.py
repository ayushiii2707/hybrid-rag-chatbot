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
corrected_query = res["corrected_query"]
expanded_query = preprocessor.expand_synonyms(corrected_query)

print("Corrected:", corrected_query)
print("Expanded:", expanded_query)

retriever = HybridRetriever()

# Let's check candidate retrieval
print("\n--- FAISS Search (unnormalized query) ---")
q_emb = retriever.generator.generate_embeddings([expanded_query])
faiss_results = retriever.vector_store.search(q_emb[0], top_k=50)
target_chunk_id = "3b97da58a590c41e2833e6360925ec9dc0349b82e177e1dadba8fbd85a089d57_c28"

found_faiss = False
for idx, r in enumerate(faiss_results):
    if r["chunk_id"] == target_chunk_id:
        print(f"Target found in FAISS at rank {idx+1} with score {r['score']:.4f}")
        found_faiss = True
        break
if not found_faiss:
    print("Target NOT found in top 50 FAISS results.")

print("\n--- BM25 Search ---")
all_chunk_ids = [c["chunk_id"] for c in retriever.keyword_ranker.chunks]
bm25_scores = retriever.keyword_ranker.score_query(expanded_query, all_chunk_ids)
sorted_bm25 = sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)
found_bm25 = False
for idx, (cid, score) in enumerate(sorted_bm25[:50]):
    if cid == target_chunk_id:
        print(f"Target found in BM25 at rank {idx+1} with score {score:.4f}")
        found_bm25 = True
        break
if not found_bm25:
    print("Target NOT found in top 50 BM25 results.")
    if target_chunk_id in bm25_scores:
        print(f"Target score in all BM25: {bm25_scores[target_chunk_id]:.4f}")

print("\n--- Hybrid Candidates (retrieve_candidate_chunks) ---")
candidates = retriever.retrieve_candidate_chunks(expanded_query, top_k=5)
found_hybrid = False
for idx, c in enumerate(candidates):
    if c["chunk_id"] == target_chunk_id:
        print(f"Target found in Hybrid candidates at rank {idx+1} with composite score {c['score']:.4f}")
        found_hybrid = True
        break
if not found_hybrid:
    print("Target NOT found in top 5 Hybrid candidates.")
    # let's print what top 5 hybrid candidates actually are
    for idx, c in enumerate(candidates[:5]):
         print(f"Rank {idx+1}: {c['chunk_id']} | Score: {c['score']:.4f} | source_file: {c['metadata']['source_file']}")
