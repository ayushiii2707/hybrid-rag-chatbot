import fitz
from pathlib import Path

pdf_dir = Path("/Users/ayushiranjan/Desktop/Chatbot/backend/datasets/raw_pdfs")
for pdf_path in pdf_dir.glob("*.pdf"):
    print(f"\nSearching: {pdf_path.name}")
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        if "micr" in text.lower():
            print(f"  Found 'micr' on page {page_num + 1}:")
            lines = text.split("\n")
            for line in lines:
                if "micr" in line.lower():
                    print(f"    {line}")
