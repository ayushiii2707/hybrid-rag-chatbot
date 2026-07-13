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
sys.path.insert(0, str(BACKEND_DIR))
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


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 HELPERS — PDF ingestion (source of truth)
# ─────────────────────────────────────────────────────────────────────────────

def ingest_pdf(
    path: Path,
    parser: PDFParser,
    cleaner: TextCleaner,
    corrector: SpellingCorrector,
    matcher: EntityMatcher,
    chunker: DocumentChunker,
) -> tuple[str, str, list]:
    """
    Runs the full ingestion pipeline on a single PDF.

    Returns:
        (doc_id, source_file_name, list_of_chunks)
    """
    logger.info(f"[Layer 1 / PDF] Ingesting: {path.name}")
    parsed_doc = parser.parse_pdf(path)
    doc_id = parsed_doc["doc_id"]
    source_file = parsed_doc["source_file"]

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
            "raw_text":    pg["text"],
            "clean_text":  clean2,
            "entities":    entities,
            "matched_vendor": resolved_vendor,
        })

    preprocessed_doc = {
        "doc_id":      doc_id,
        "source_file": source_file,
        "pages":       preprocessed_pages,
    }

    chunks = chunker.chunk_document(preprocessed_doc)

    # Tag every PDF chunk with its layer so it's distinguishable downstream
    for chunk in chunks:
        chunk.setdefault("metadata", {})["layer"] = "pdf_source"

    logger.info(
        f"[Layer 1 / PDF] {path.name} → doc_id={doc_id[:12]}… "
        f"| {len(parsed_doc['pages'])} pages | {len(chunks)} chunks"
    )
    return doc_id, source_file, chunks


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2 HELPERS — FAQ JSON supplement (dependent on Layer 1)
# ─────────────────────────────────────────────────────────────────────────────

def ingest_faq_supplement(
    json_path: Path,
    mapped_pdf_name: str,
    pdf_doc_id: str,
) -> list:
    """
    Converts a structured FAQ JSON file into supplemental chunks that are
    linked to the parent PDF document via its real doc_id.

    This is strictly a supplement — it must only be called after Layer 1 has
    successfully parsed the matching PDF and returned a real doc_id.

    Each FAQ entry becomes one chunk:
        text = "Question: <q>\\nAnswer: <a>"

    The chunk metadata carries:
        layer              = "faq_supplement"   (distinguishes from PDF chunks)
        alternate_phrasings (for full-text search boost)
        section_title / subsection_title derived from FAQ category
    """
    logger.info(
        f"[Layer 2 / FAQ] Ingesting supplement: {json_path.name} "
        f"→ linked to PDF '{mapped_pdf_name}' (doc_id={pdf_doc_id[:12]}…)"
    )
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"[Layer 2 / FAQ] Failed to load {json_path}: {e}")
        return []

    faq_chunks = []
    faqs = data.get("faqs", [])

    for idx, faq in enumerate(faqs):
        intent      = faq.get("intent", f"intent_{idx}")
        category    = faq.get("category", "general")
        question    = faq.get("question", "")
        answer      = faq.get("answer", "")
        alt_phrases = faq.get("alternate_phrasings", [])

        chunk_text = f"Question: {question}\nAnswer: {answer}"

        chunk = {
            "chunk_id":    f"{pdf_doc_id}_faq_{intent}",
            "doc_id":      pdf_doc_id,          # ← real PDF doc_id (not a hash of JSON filename)
            "source_file": mapped_pdf_name,
            "page_number": 1,
            "chunk_index": idx,
            "text":        chunk_text,
            "metadata": {
                "source_file":          mapped_pdf_name,
                "page_number":          1,
                "char_count":           len(chunk_text),
                "layer":                "faq_supplement",   # ← layer tag
                "section_title":        "FAQ",
                "subsection_title":     category,
                "procedure_id":         f"faq_{intent}",
                "chunk_position":       "start",
                "page_order":           0,
                "detected_step_numbers": [],
                "alternate_phrasings":  alt_phrases,
            },
        }
        faq_chunks.append(chunk)

    logger.info(
        f"[Layer 2 / FAQ] {json_path.name} → {len(faq_chunks)} supplement chunks"
    )
    return faq_chunks


# ─────────────────────────────────────────────────────────────────────────────
# RETRIEVAL TEST HELPER
# ─────────────────────────────────────────────────────────────────────────────

def test_retrieval(engine: RetrievalEngine, query: str) -> None:
    print(f"\nQUERY: \"{query}\"")
    print("─" * 80)

    results = engine.retrieve(query, top_k=3, threshold=0.3)
    if not results:
        print("  (No relevant chunks matched the threshold)")
        return

    for i, res in enumerate(results):
        score  = res["score"]
        source = res["metadata"]["source_file"]
        page   = res["metadata"]["page_number"]
        layer  = res["metadata"].get("layer", "unknown")
        cid    = res["chunk_id"]
        snippet = res["text"].replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"
        print(
            f"  Rank {i+1} [Score: {score:.4f}] [{layer}] "
            f"— File: {source} (Page {page}) [ID: {cid}]"
        )
        print(f"    Snippet: \"{snippet}\"\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 80)
    print("  HYBRID RAG INDEXING PIPELINE")
    print("  Layer 1: PDF source of truth  |  Layer 2: FAQ supplement")
    print("=" * 80)

    raw_pdf_dir = BACKEND_DIR / "datasets" / "raw_pdfs"
    config_path = BACKEND_DIR / "embeddings" / "config.json"

    # ── Initialise all pipeline components ───────────────────────────────────
    logger.info("Initialising ingestion, preprocessing and chunking components…")
    loader   = PDFLoader(default_directory=raw_pdf_dir)
    parser   = PDFParser()
    cleaner  = TextCleaner()
    corrector = SpellingCorrector()
    matcher  = EntityMatcher()
    chunker  = DocumentChunker(strategy="recursive", chunk_size=500, chunk_overlap=50)

    # ── LAYER 1: Ingest PDFs ─────────────────────────────────────────────────
    print("\n" + "─" * 80)
    print("  LAYER 1 — PDF Ingestion (Source of Truth)")
    print("─" * 80)

    pdf_paths = loader.load_from_directory()
    if not pdf_paths:
        logger.error(f"No PDFs found in {raw_pdf_dir}. Cannot proceed — PDFs are required.")
        sys.exit(1)
    logger.info(f"Discovered {len(pdf_paths)} PDF(s): {[p.name for p in pdf_paths]}")

    # Maps  pdf_filename → doc_id  (used by Layer 2 to link FAQs)
    pdf_name_to_doc_id: dict[str, str] = {}
    all_chunks: list = []
    pdf_chunk_count = 0

    for path in pdf_paths:
        doc_id, source_file, chunks = ingest_pdf(
            path, parser, cleaner, corrector, matcher, chunker
        )
        pdf_name_to_doc_id[source_file] = doc_id
        all_chunks.extend(chunks)
        pdf_chunk_count += len(chunks)

    logger.info(
        f"Layer 1 complete — {len(pdf_paths)} PDF(s) → {pdf_chunk_count} chunks "
        f"| doc_ids: {list(pdf_name_to_doc_id.keys())}"
    )

    # ── LAYER 2: Ingest FAQ supplements ──────────────────────────────────────
    print("\n" + "─" * 80)
    print("  LAYER 2 — FAQ Supplement (Dependent on Layer 1)")
    print("─" * 80)

    # Each entry maps:  json_filename → exact PDF source_file name it supplements
    faq_manifest = [
        ("delivery_location_faq.json",    "Add Delivery Location User Manual.pdf"),
        ("registration_manual_faq.json",  "registration manual.pdf"),
    ]

    faq_chunk_count = 0
    for faq_filename, mapped_pdf_name in faq_manifest:
        # Enforce dependency: only ingest FAQ if its parent PDF was processed
        if mapped_pdf_name not in pdf_name_to_doc_id:
            logger.warning(
                f"[Layer 2 / FAQ] Skipping '{faq_filename}' — "
                f"parent PDF '{mapped_pdf_name}' was not found or failed to ingest."
            )
            continue

        faq_path = BACKEND_DIR / "datasets" / faq_filename
        if not faq_path.exists():
            logger.warning(f"[Layer 2 / FAQ] File not found: {faq_path}")
            continue

        real_doc_id = pdf_name_to_doc_id[mapped_pdf_name]
        faq_chunks  = ingest_faq_supplement(faq_path, mapped_pdf_name, real_doc_id)
        all_chunks.extend(faq_chunks)
        faq_chunk_count += len(faq_chunks)

    logger.info(
        f"Layer 2 complete — {faq_chunk_count} FAQ supplement chunks added."
    )

    total_chunks = len(all_chunks)
    logger.info(
        f"Total chunks ready for embedding: {total_chunks} "
        f"({pdf_chunk_count} PDF + {faq_chunk_count} FAQ)"
    )

    # ── Reset DB and index for a clean validation run ─────────────────────────
    from backend.database.db import SessionLocal
    from backend.auth.auth_models import Chunk, Document, VectorMap
    db = SessionLocal()
    try:
        db.query(VectorMap).delete()
        db.query(Chunk).delete()
        db.query(Document).delete()
        db.commit()
        logger.info("Cleared PostgreSQL tables for clean validation run.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear database: {e}")
    finally:
        db.close()

    # Remove stale index files
    idx_p  = os.path.join(os.path.dirname(__file__), "faiss_index.bin")
    meta_p = os.path.join(os.path.dirname(__file__), "metadata.json")
    for f in (idx_p, meta_p):
        if os.path.exists(f):
            os.remove(f)

    # ── Embed and index all chunks ────────────────────────────────────────────
    print("\n" + "─" * 80)
    print("  EMBEDDING & INDEXING")
    print("─" * 80)

    logger.info("Initialising EmbeddingGenerator and FAISSVectorStore…")
    generator    = EmbeddingGenerator(config_path=str(config_path))
    vector_store = FAISSVectorStore(config_path=str(config_path))

    logger.info(f"Generating embeddings for {total_chunks} chunks…")
    chunks_with_embeddings = generator.embed_chunks(all_chunks)
    embeddings_np = np.array(
        [c["embedding"] for c in chunks_with_embeddings], dtype=np.float32
    )

    logger.info("Indexing embeddings into FAISS Vector Store…")
    vector_store.add_embeddings(embeddings_np, all_chunks)

    # ── Validation Suite ──────────────────────────────────────────────────────
    print("\n" + "─" * 80)
    print("  VALIDATION SUITE")
    print("─" * 80)

    # Validation A: Duplicate Vector Protection
    count_before = vector_store.index.ntotal
    vector_store.add_embeddings(embeddings_np, all_chunks)
    count_after  = vector_store.index.ntotal
    assert count_before == count_after, (
        f"Duplicate prevention failed — index grew from {count_before} to {count_after}."
    )
    print(f"✓ Validation A: Duplicate protection — index stable at {count_before} vectors.")

    # Validation B: Disk Persistence and Reload
    vector_store.save_index()
    assert os.path.exists(idx_p),  "faiss_index.bin was not saved."
    assert os.path.exists(meta_p), "metadata.json was not saved."

    reloaded_store = FAISSVectorStore(config_path=str(config_path))
    reloaded_store.load_index()
    assert reloaded_store.index is not None
    assert reloaded_store.index.ntotal == count_before, (
        f"Reload mismatch: {reloaded_store.index.ntotal} vs {count_before}"
    )
    print("✓ Validation B: Disk persistence and reload integrity verified.")

    # Validation C: Retrieval Equivalence (original vs reloaded store)
    q_text   = "FSSAI license check online portal"
    q_vector = generator.generate_embeddings([q_text])[0]
    res_orig   = vector_store.search(q_vector, top_k=2)
    res_reload = reloaded_store.search(q_vector, top_k=2)
    assert len(res_orig) == len(res_reload)
    for r1, r2 in zip(res_orig, res_reload):
        assert r1["chunk_id"] == r2["chunk_id"]
        assert abs(r1["score"] - r2["score"]) < 1e-5
    print("✓ Validation C: Reloaded store search equivalence verified.")

    # Validation D: DB consistency — expected 2 documents, correct chunk counts
    db = SessionLocal()
    try:
        doc_count    = db.query(Document).count()
        chunk_count  = db.query(Chunk).count()
        vmap_count   = db.query(VectorMap).count()

        assert doc_count == 2, f"Expected 2 documents in DB, got {doc_count}."
        assert chunk_count == total_chunks, (
            f"Expected {total_chunks} chunks in DB, got {chunk_count}."
        )
        assert vmap_count == total_chunks, (
            f"Expected {total_chunks} vector maps, got {vmap_count}."
        )
        print(
            f"✓ Validation D: DB consistency — "
            f"{doc_count} docs | {chunk_count} chunks | {vmap_count} vector maps."
        )
    finally:
        db.close()

    # Validation E: Semantic accuracy — layer-aware document context mapping
    engine = RetrievalEngine(
        generator=generator, vector_store=reloaded_store, config_path=str(config_path)
    )

    # "in-house consumption" should surface from the PDF layer (page 2 of Add Delivery Location)
    res_pdf = engine.retrieve(
        "in-house consumption Nature of Article and Services", top_k=5, threshold=0.2
    )
    pdf_match = next(
        (r for r in res_pdf
         if "Add Delivery Location User Manual.pdf" in r["metadata"]["source_file"]
         and r["metadata"].get("layer") == "pdf_source"),
        None
    )
    assert pdf_match is not None, (
        "Did not retrieve any pdf_source layer match for 'in-house consumption'."
    )
    print(
        f"✓ Validation E (PDF layer): Matched '{pdf_match['metadata']['source_file']}' "
        f"page {pdf_match['metadata']['page_number']} via pdf_source layer."
    )

    # "process purpose" should surface from the FAQ supplement layer
    res_faq = engine.retrieve(
        "What is the Add Delivery Location process for?", top_k=5, threshold=0.2
    )
    faq_match = next(
        (r for r in res_faq
         if r["metadata"].get("layer") == "faq_supplement"),
        None
    )
    assert faq_match is not None, (
        "Did not retrieve any faq_supplement layer match for process purpose query."
    )
    print(
        f"✓ Validation E (FAQ layer): Matched chunk '{faq_match['chunk_id']}' "
        f"via faq_supplement layer."
    )

    # ── Semantic search experiments ───────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  SEMANTIC SEARCH EXPERIMENTS")
    print("=" * 80)

    test_queries = [
        "UDYAM registration format and validation rules",
        "How can a supplier check FSSAI active status",
        "reliance retail limited merchandise supplier",
        "are items for in-house consumption supported by the app",
        "onboarding timeline and approval contact email",
        "What is this portal for?",
        "What is the Add Delivery Location process for?",
    ]
    for query in test_queries:
        test_retrieval(engine, query)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  INTEGRATION SUCCESS: ALL VALIDATIONS PASSED")
    print(f"  {pdf_chunk_count} PDF chunks (source of truth) + "
          f"{faq_chunk_count} FAQ chunks (supplement) = {total_chunks} total")
    print("=" * 80)


if __name__ == "__main__":
    main()
