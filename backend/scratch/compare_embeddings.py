import os
import sys
import json
import numpy as np

# Bootstrap Paths
BACKEND_DIR = "/Users/ayushiranjan/Desktop/Chatbot/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "embeddings"))

from embedding_generator import EmbeddingGenerator

generator = EmbeddingGenerator()
query = "how to input micr code in bank details bank routing code magnetic ink character recognition"
q_emb = generator.generate_embeddings([query])[0]

# Load metadata.json
with open("/Users/ayushiranjan/Desktop/Chatbot/backend/embeddings/metadata.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

target_id = "3b97da58a590c41e2833e6360925ec9dc0349b82e177e1dadba8fbd85a089d57_c28"
target_chunk = None
for c in chunks:
    if c["chunk_id"] == target_id:
        target_chunk = c
        break

if target_chunk:
    chunk_emb = np.array(target_chunk["embedding"], dtype=np.float32)
    # L2 normalize
    q_norm = q_emb / np.linalg.norm(q_emb)
    c_norm = chunk_emb / np.linalg.norm(chunk_emb)
    
    similarity = np.dot(q_norm, c_norm)
    print(f"Manual cosine similarity between query and chunk: {similarity:.4f}")
else:
    print("Target chunk not found in metadata.")
