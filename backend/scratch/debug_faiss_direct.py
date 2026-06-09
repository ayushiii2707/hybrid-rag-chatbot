import os
import sys
import numpy as np

# Bootstrap Paths
BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))

from embedding_generator import EmbeddingGenerator
from vector_store import FAISSVectorStore

generator = EmbeddingGenerator()
vector_store = FAISSVectorStore()
vector_store.load_index()

query = "how to input micr code in bank details bank routing code magnetic ink character recognition"
q_emb = generator.generate_embeddings([query])[0]
raw_matches = vector_store.search(q_emb, top_k=30)

print(f"Index total vectors: {vector_store.index.ntotal}")
print("\n--- Direct FAISS Search Top 30 ---")
for idx, m in enumerate(raw_matches):
    print(f"Rank {idx+1}: {m['chunk_id']} | Score: {m['score']:.4f} | source_file: {m['metadata']['source_file']}")
