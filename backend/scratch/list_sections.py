import json

with open("/Users/ayushiranjan/Desktop/Chatbot/backend/embeddings/metadata.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

sections_by_doc = {}
for chunk in chunks:
    source_file = chunk.get("source_file") or chunk.get("metadata", {}).get("source_file")
    section_title = chunk.get("metadata", {}).get("section_title")
    subsection_title = chunk.get("metadata", {}).get("subsection_title")
    
    if source_file not in sections_by_doc:
        sections_by_doc[source_file] = set()
    
    sections_by_doc[source_file].add((section_title, subsection_title))

for doc, sections in sections_by_doc.items():
    print(f"\nDocument: {doc}")
    sorted_sections = sorted(list(sections), key=lambda x: (str(x[0]), str(x[1])))
    for sec, subsec in sorted_sections:
        print(f"  Section: {sec} | Subsection: {subsec}")
