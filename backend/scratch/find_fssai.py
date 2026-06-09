import json

with open("/Users/ayushiranjan/Desktop/Chatbot/backend/embeddings/metadata.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

for c in chunks:
    if "fssai" in c["text"].lower() and "portal" in c["text"].lower():
        print(f"Chunk ID: {c['chunk_id']}")
        print(f"Text:\n{c['text']}\n")
