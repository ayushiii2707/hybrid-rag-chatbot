import os, sys
# Ensure backend root and relevant subfolders are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
# Add subfolders for imports
subfolders = ['embeddings', 'retrieval_intelligence', 'query_engine']
for sub in subfolders:
    path = os.path.join(BASE_DIR, sub)
    if path not in sys.path:
        sys.path.insert(0, path)

from embeddings.embedding_generator import EmbeddingGenerator
from embeddings.vector_store import FAISSVectorStore
from retrieval_intelligence.keyword_ranker import KeywordRanker
from retrieval_intelligence.hybrid_retriever import HybridRetriever
from query_engine.context_assembler import ContextAssembler

QUERY = "where to click for new registration"
TARGET_CHUNK_ID = "3953124eac5f11b709b4d0a6e920c14f97f925e38323d78625a3d4dd97c3e16b_faq_start_new_registration"

# Stage 3: Embedding Storage
vector_store = FAISSVectorStore()
metadata_entry = next((m for m in vector_store.metadata_list if m.get('chunk_id') == TARGET_CHUNK_ID), None)
vector_id = None
embedding_exists = False
if metadata_entry:
    vector_id = vector_store.metadata_list.index(metadata_entry)
    # FAISS stores vectors separately; we assume embedding exists if metadata present
    embedding_exists = True
print("--- Stage 3: Embedding Storage ---")
print(f"chunk_id: {TARGET_CHUNK_ID}")
print(f"vector_id (FAISS index): {vector_id}")
print(f"embedding exists: {embedding_exists}")
print(f"embedding metadata: {metadata_entry.get('metadata', {})}\n")

# Stage 4: Vector Retrieval (FAISS)
embed_gen = EmbeddingGenerator()
query_embedding = embed_gen.generate_embeddings([QUERY])
semantic_results = vector_store.search(query_embedding[0], top_k=20)
print("--- Stage 4: FAISS Top 20 Results ---")
for idx, res in enumerate(semantic_results, 1):
    print(f"{idx}. chunk_id={res['chunk_id']} score={res['score']:.4f}")
faiss_rank = next((i+1 for i, r in enumerate(semantic_results) if r['chunk_id'] == TARGET_CHUNK_ID), None)
print(f"Target chunk FAISS rank: {faiss_rank}\n")

# Stage 5: BM25 Retrieval
ranker = KeywordRanker()
all_chunk_ids = [c["chunk_id"] for c in ranker.chunks]
bm25_scores = ranker.score_query(QUERY, all_chunk_ids)
sorted_bm25 = sorted(bm25_scores.items(), key=lambda kv: kv[1], reverse=True)[:20]
print("--- Stage 5: BM25 Top 20 Results ---")
for idx, (cid, score) in enumerate(sorted_bm25, 1):
    print(f"{idx}. chunk_id={cid} score={score:.4f}")
bm25_rank = next((i+1 for i, (cid, _) in enumerate(sorted_bm25) if cid == TARGET_CHUNK_ID), None)
print(f"Target chunk BM25 rank: {bm25_rank}\n")

# Stage 6 & 7: Hybrid Fusion and Reranking
retriever = HybridRetriever()
hybrid_results = retriever.retrieve_best_chunk(QUERY, top_k=20)
print("--- Stage 6: Hybrid Fusion Top 20 (pre-rerank) ---")
# Pre-rerank info is in retriever.last_query_debug['hybrid_results']
pre_hybrid = retriever.last_query_debug.get('hybrid_results', [])
for idx, cand in enumerate(pre_hybrid[:20], 1):
    print(f"{idx}. chunk_id={cand['chunk_id']} faiss_score={cand['faiss_score']:.4f} bm25_score={cand['bm25_score']:.4f}")
print("--- Stage 7: Reranked Top 20 ---")
for idx, res in enumerate(hybrid_results, 1):
    print(f"{idx}. chunk_id={res['chunk_id']} composite_score={res['score']:.4f}")
rerank_rank = next((i+1 for i, c in enumerate(hybrid_results) if c['chunk_id'] == TARGET_CHUNK_ID), None)
print(f"Target chunk rank after rerank: {rerank_rank}\n")

# Stage 8: Context Assembly
assembler = ContextAssembler()
assembled = assembler.assemble(QUERY, hybrid_results, query_granularity='factual')
print("--- Stage 8: Assembled Context ---")
print(assembled['assembled_context'])
# Check inclusion
included = TARGET_CHUNK_ID in [c['chunk_id'] for c in hybrid_results]
print(f"Target chunk included in final context: {included}\n")

# Stage 9: Prompt Construction
prompt = f"You are a helpful assistant. Answer the following question using the provided context.\n\nContext:\n{assembled['assembled_context']}\n\nQuestion: {QUERY}\n"
print("--- Stage 9: Prompt ---")
print(prompt)
contains_answer = "New Supplier Registration" in prompt
print(f"Prompt contains expected answer phrase: {contains_answer}\n")

# Stage 10: Generation (simulated)
print("--- Stage 10: Generation Output (simulated) ---")
print(assembled['assembled_context'])
