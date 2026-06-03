import json
import logging
import os
import sys
from pathlib import Path
import numpy as np

# Set up clean logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("verify_embeddings")

# ── Bootstrap Paths ───────────────────────────────────────────────────────────
# backend/embeddings/verify_embeddings.py -> parent.parent is backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR / "ingestion"))
sys.path.insert(0, str(BACKEND_DIR / "preprocessing"))
sys.path.insert(0, str(BACKEND_DIR / "chunking"))
sys.path.insert(0, str(BACKEND_DIR / "embeddings"))

try:
    from pdf_loader import PDFLoader
    from pdf_parser import PDFParser
    from text_cleaner import TextCleaner
    from spelling_corrector import SpellingCorrector
    from entity_matcher import EntityMatcher
    from text_splitter import DocumentChunker
    from embedding_generator import EmbeddingGenerator
    from vector_store import FAISSVectorStore
    from retrieval_engine import RetrievalEngine
except ImportError as e:
    logger.critical(f"Failed to import pipeline dependencies: {e}")
    sys.exit(1)


def test_retrieval(engine: RetrievalEngine, query: str) -> None:
    print(f"\nQUERY: \"{query}\"")
    print("─" * 80)
    
    results = engine.retrieve(query, top_k=3, threshold=0.3)
    if not results:
        print("  (No relevant chunks matched the threshold query requirements)")
        return
        
    for i, res in enumerate(results):
        score = res["score"]
        source = res["metadata"]["source_file"]
        page = res["metadata"]["page_number"]
        chunk_id = res["chunk_id"]
        # Print rank, score, source, page, chunk details
        print(f"  Rank {i+1} [Score: {score:.4f}] — File: {source} (Page {page}) [ID: {chunk_id}]")
        snippet = res["text"].replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        print(f"    Snippet: \"{snippet}\"\n")


def main() -> None:
    print("=" * 80)
    print("  RUNNING SEMANTIC RETRIEVAL INTEGRATION & VERIFICATION PIPELINE")
    print("=" * 80)

    raw_pdf_dir = BACKEND_DIR / "datasets" / "raw_pdfs"
    config_path = BACKEND_DIR / "embeddings" / "config.json"

    # 1. Initialize Pipeline Components
    logger.info("Initializing ingestion, preprocessing and chunking components...")
    loader = PDFLoader(default_directory=raw_pdf_dir)
    parser = PDFParser()
    cleaner = TextCleaner()
    corrector = SpellingCorrector()
    matcher = EntityMatcher()
    chunker = DocumentChunker(strategy="recursive", chunk_size=500, chunk_overlap=50)

    # 2. Run PDF Discovery
    pdf_paths = loader.load_from_directory()
    if not pdf_paths:
        logger.error(f"No PDFs found in directory {raw_pdf_dir}. Cannot proceed.")
        sys.exit(1)
    logger.info(f"Discovered {len(pdf_paths)} raw PDF(s) for ingestion.")

    # 3. Parse, Preprocess, and Chunk PDFs
    all_chunks = []
    for path in pdf_paths:
        logger.info(f"Ingesting & processing document: {path.name}")
        parsed_doc = parser.parse_pdf(path)
        
        preprocessed_pages = []
        for pg in parsed_doc["pages"]:
            clean1 = cleaner.clean(pg["text"])
            clean2 = corrector.correct_text(clean1)
            entities = matcher.extract_entities(clean2)
            
            resolved_vendor = None
            for ent in entities:
                if ent["label"] == "ORG":
                    v = matcher.match_vendor(ent["text"])
                    if v:
                        resolved_vendor = v
                        break
            
            preprocessed_pages.append({
                "page_number": pg["page_number"],
                "raw_text": pg["text"],
                "clean_text": clean2,
                "entities": entities,
                "matched_vendor": resolved_vendor,
            })
            
        preprocessed_doc = {
            "doc_id": parsed_doc["doc_id"],
            "source_file": parsed_doc["source_file"],
            "pages": preprocessed_pages,
        }
        
        doc_chunks = chunker.chunk_document(preprocessed_doc)
        all_chunks.extend(doc_chunks)
        logger.info(f"Document {path.name} processed into {len(doc_chunks)} chunks.")

    logger.info(f"Total chunks generated across all documents: {len(all_chunks)}")

    # 4. Initialize Embedding and Vector Store Layers
    logger.info("Initializing EmbeddingGenerator and FAISSVectorStore...")
    generator = EmbeddingGenerator(config_path=str(config_path))
    vector_store = FAISSVectorStore(config_path=str(config_path))

    # Reset any existing index file to start fresh for validation
    idx_p = vector_store.index_path
    meta_p = vector_store.metadata_path
    if os.path.exists(idx_p):
        os.remove(idx_p)
    if os.path.exists(meta_p):
        os.remove(meta_p)
    logger.info("Cleared pre-existing index files on disk to perform clean validation.")

    # 5. Generate and Add Embeddings
    logger.info("Generating embeddings for all chunks...")
    chunks_with_embeddings = generator.embed_chunks(all_chunks)
    
    # Extract raw arrays
    embeddings_list = [c["embedding"] for c in chunks_with_embeddings]
    embeddings_np = np.array(embeddings_list, dtype=np.float32)
    
    logger.info("Indexing embeddings into FAISS Vector Store...")
    vector_store.add_embeddings(embeddings_np, all_chunks)

    # 6. Verify Vector Store Validations
    print("\n--- Running Vector Store Validations ---")
    
    # Validation A: Duplicate Vector Protection
    count_before = vector_store.index.ntotal
    logger.info(f"Vector count before duplicate insert attempt: {count_before}")
    logger.info("Attempting to insert the same chunk data again...")
    vector_store.add_embeddings(embeddings_np, all_chunks)
    count_after = vector_store.index.ntotal
    logger.info(f"Vector count after duplicate insert attempt: {count_after}")
    
    assert count_before == count_after, (
        f"Validation Failed: Duplicate prevention did not block insertion! "
        f"Index size grew from {count_before} to {count_after}."
    )
    print("✓ Validation A: Duplicate Vector Protection passed (Index size remained stable).")

    # Validation B: Index Persistence and Reload Integrity
    logger.info("Saving index and metadata to disk...")
    vector_store.save_index()
    
    assert os.path.exists(idx_p), "Index file was not saved."
    assert os.path.exists(meta_p), "Metadata JSON file was not saved."
    
    logger.info("Re-initializing a fresh FAISSVectorStore from persisted index files...")
    reloaded_store = FAISSVectorStore(config_path=str(config_path))
    reloaded_store.load_index()
    
    assert reloaded_store.index is not None, "Reloaded index is Null."
    assert reloaded_store.index.ntotal == count_before, (
        f"Validation Failed: Reloaded index size mismatch ({reloaded_store.index.ntotal} vs {count_before})."
    )
    print("✓ Validation B: Disk Persistence and Alignment Reload passed.")

    # Validation C: Retrieval Equivalence
    # Ensure reloaded store produces exactly identical results as the original store
    query_text = "FSSAI license check online portal"
    q_vector = generator.generate_embeddings([query_text])[0]
    res_orig = vector_store.search(q_vector, top_k=2)
    res_reload = reloaded_store.search(q_vector, top_k=2)
    
    assert len(res_orig) == len(res_reload), "Mismatch in count of results."
    for r1, r2 in zip(res_orig, res_reload):
        assert r1["chunk_id"] == r2["chunk_id"], "Mismatch in retrieved chunk IDs."
        assert abs(r1["score"] - r2["score"]) < 1e-5, "Mismatch in cosine similarity scores."
    print("✓ Validation C: Reloaded Index Search Equivalence verified successfully.")

    # 7. Initialize Retrieval Engine
    # Initialize RetrievalEngine using our verified reloaded_store
    engine = RetrievalEngine(generator=generator, vector_store=reloaded_store, config_path=str(config_path))

    # 8. Run Retrieval Queries
    print("\n" + "=" * 80)
    print("  RUNNING SEMANTIC SEARCH RETRIEVAL EXPERIMENTS")
    print("=" * 80)

    # List of queries testing spelling correction and business logic domain
    test_queries = [
        "UDYAM registration format and validation rules",
        "How can a supplier check FSSAI active status",
        "reliance retail limited merchandise supplier",
        "are items for in-house consumption supported by the app",
        "onboarding timeline and approval contact email"
    ]

    for query in test_queries:
        test_retrieval(engine, query)

    # 9. Verify Specific Retrieval Correctness
    # "in-house consumption" should match page 2 of Add Delivery Location User Manual.pdf
    res_in_house = engine.retrieve("in-house consumption in Nature and Services", top_k=1, threshold=0.2)
    assert res_in_house, "Did not retrieve any match for in-house consumption"
    best_match = res_in_house[0]
    assert "Add Delivery Location User Manual.pdf" in best_match["metadata"]["source_file"], "Failed to match correct file source."
    assert best_match["metadata"]["page_number"] == 2, f"Failed to match correct page. Expected page 2, got page {best_match['metadata']['page_number']}."
    print("\n✓ Validation D: Semantic accuracy of document context mapping passed.")

    print("\n" + "=" * 80)
    print("  INTEGRATION SUCCESS: ALL EMBEDDING & RETRIEVAL VALIDATIONS PASSED")
    print("=" * 80)


if __name__ == "__main__":
    main()
