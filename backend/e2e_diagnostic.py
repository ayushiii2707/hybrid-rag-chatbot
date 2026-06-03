"""
Full End-to-End Pipeline Diagnostic
Runs ALL PDFs in backend/datasets/raw_pdfs/ through:
  Ingestion → Preprocessing → Chunking

Displays:
  - Detected filenames
  - Extracted page previews
  - Cleaned text previews
  - Entity extraction results
  - Generated chunks
  - Chunk counts per document
  - Metadata validation table
"""

import json
import sys
import os
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent   # backend/
sys.path.insert(0, str(BACKEND_DIR / "ingestion"))
sys.path.insert(0, str(BACKEND_DIR / "preprocessing"))
sys.path.insert(0, str(BACKEND_DIR / "chunking"))

from pdf_loader import PDFLoader
from pdf_parser import PDFParser
from text_cleaner import TextCleaner
from spelling_corrector import SpellingCorrector
from entity_matcher import EntityMatcher
from text_splitter import DocumentChunker

RAW_PDF_DIR = BACKEND_DIR / "datasets" / "raw_pdfs"
DIVIDER = "─" * 72
SECTION  = "═" * 72

CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50
STRATEGY      = "recursive"  # change to "page" for page-level mode

PREVIEW_CHARS = 300   # how many chars to preview per page / chunk


def section(title: str) -> None:
    print(f"\n{SECTION}")
    print(f"  {title}")
    print(SECTION)


def sub(title: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def truncate(text: str, n: int = PREVIEW_CHARS) -> str:
    text = text.strip()
    if len(text) <= n:
        return repr(text)
    return repr(text[:n]) + f"  ... [{len(text) - n} more chars]"


def validate_metadata(chunk: dict) -> list:
    """Return a list of metadata error strings (empty = OK)."""
    errs = []
    if chunk["metadata"]["char_count"] != len(chunk["text"]):
        errs.append(f"char_count mismatch ({chunk['metadata']['char_count']} vs {len(chunk['text'])})")
    if chunk["metadata"]["page_number"] != chunk["page_number"]:
        errs.append(f"page_number mismatch")
    if chunk["metadata"]["source_file"] != chunk["source_file"]:
        errs.append(f"source_file mismatch")
    if not chunk["chunk_id"].startswith(chunk["doc_id"]):
        errs.append(f"chunk_id does not derive from doc_id")
    return errs


def main() -> None:
    global_errors   = []
    total_chunks    = 0

    # ── INIT PIPELINE COMPONENTS ─────────────────────────────────────────────
    section("INITIALISING PIPELINE COMPONENTS")
    loader    = PDFLoader(default_directory=RAW_PDF_DIR)
    parser    = PDFParser()
    cleaner   = TextCleaner()
    corrector = SpellingCorrector()
    matcher   = EntityMatcher()
    chunker   = DocumentChunker(
        strategy=STRATEGY,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    print("  PDFLoader        ✓")
    print("  PDFParser        ✓")
    print("  TextCleaner      ✓")
    print("  SpellingCorrector✓")
    print("  EntityMatcher    ✓")
    print(f"  DocumentChunker  ✓  (strategy={STRATEGY}, size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    # ── STEP 1: DISCOVER PDFs ────────────────────────────────────────────────
    section("STEP 1 — PDF DISCOVERY")
    pdf_paths = loader.load_from_directory()
    if not pdf_paths:
        print("  ✗ No PDFs found. Aborting.")
        sys.exit(1)

    print(f"  Directory : {RAW_PDF_DIR}")
    print(f"  Found     : {len(pdf_paths)} PDF(s)\n")
    for p in pdf_paths:
        size_kb = p.stat().st_size / 1024
        print(f"    [{size_kb:7.1f} KB]  {p.name}")

    # ── PROCESS EACH PDF ─────────────────────────────────────────────────────
    for pdf_path in pdf_paths:
        doc_name = pdf_path.name

        section(f"DOCUMENT: {doc_name}")

        # ── STEP 2: INGESTION ────────────────────────────────────────────────
        sub("STEP 2 — INGESTION  (load + parse)")
        try:
            parsed_doc = parser.parse_pdf(pdf_path)
        except Exception as e:
            err = f"[{doc_name}] Ingestion failed: {e}"
            global_errors.append(err)
            print(f"  ✗ {err}")
            continue

        print(f"  doc_id      : {parsed_doc['doc_id']}")
        print(f"  source_file : {parsed_doc['source_file']}")
        print(f"  pages found : {len(parsed_doc['pages'])}")

        for pg in parsed_doc["pages"]:
            print(f"\n  ── Page {pg['page_number']} raw text preview:")
            print(f"     {truncate(pg['text'], PREVIEW_CHARS)}")

        # ── STEP 3: PREPROCESSING ────────────────────────────────────────────
        sub("STEP 3 — PREPROCESSING  (clean → spell-correct → entities)")

        preprocessed_pages = []
        for pg in parsed_doc["pages"]:
            raw_text = pg["text"]
            clean1   = cleaner.clean(raw_text)
            clean2   = corrector.correct_text(clean1)
            entities = matcher.extract_entities(clean2)

            # Resolve vendor
            resolved_vendor = None
            for ent in entities:
                if ent["label"] == "ORG":
                    v = matcher.match_vendor(ent["text"])
                    if v:
                        resolved_vendor = v
                        break

            preprocessed_pages.append({
                "page_number"    : pg["page_number"],
                "raw_text"       : raw_text,
                "clean_text"     : clean2,
                "entities"       : entities,
                "matched_vendor" : resolved_vendor,
            })

            print(f"\n  ── Page {pg['page_number']}")
            print(f"     clean_text preview : {truncate(clean2, PREVIEW_CHARS)}")

            if entities:
                print(f"     entities ({len(entities)}):")
                for ent in entities[:10]:   # cap at 10 per page
                    print(f"       {ent['label']:<12} {repr(ent['text'])}")
                if len(entities) > 10:
                    print(f"       ... and {len(entities) - 10} more")
            else:
                print(f"     entities : (none detected)")

            print(f"     matched_vendor : {resolved_vendor}")

        preprocessed_doc = {
            "doc_id"      : parsed_doc["doc_id"],
            "source_file" : parsed_doc["source_file"],
            "pages"       : preprocessed_pages,
        }

        # ── STEP 4: CHUNKING ─────────────────────────────────────────────────
        sub("STEP 4 — CHUNKING")
        try:
            chunks = chunker.chunk_document(preprocessed_doc)
        except Exception as e:
            err = f"[{doc_name}] Chunking failed: {e}"
            global_errors.append(err)
            print(f"  ✗ {err}")
            continue

        doc_chunk_count = len(chunks)
        total_chunks   += doc_chunk_count

        print(f"  Total chunks produced : {doc_chunk_count}")

        # Show first 3 and last 1 chunk
        preview_chunks = chunks[:3] + (chunks[-1:] if len(chunks) > 3 else [])
        shown_last = len(chunks) > 3

        for i, chunk in enumerate(preview_chunks):
            if shown_last and i == 3:
                print(f"\n  ── ... ({doc_chunk_count - 3} chunks omitted) ...")
            print(f"\n  ── Chunk [{chunk['chunk_index']}]")
            print(f"     chunk_id    : {chunk['chunk_id']}")
            print(f"     page_number : {chunk['page_number']}")
            print(f"     char_count  : {chunk['metadata']['char_count']}")
            print(f"     text        : {truncate(chunk['text'], 200)}")

        # ── METADATA VALIDATION TABLE ─────────────────────────────────────
        sub("STEP 5 — METADATA VALIDATION TABLE")
        errs_found = False
        header = f"  {'Idx':<5} {'Page':<5} {'meta.chars':<12} {'len(text)':<12} {'meta.page':<11} {'meta.src':<30} {'Status'}"
        print(header)
        print("  " + "─" * (len(header) - 2))
        for chunk in chunks:
            errs = validate_metadata(chunk)
            status = "✓ OK" if not errs else "✗ " + "; ".join(errs)
            if errs:
                errs_found = True
                global_errors.append(f"[{doc_name}] chunk {chunk['chunk_id']}: {'; '.join(errs)}")
            print(
                f"  {chunk['chunk_index']:<5} "
                f"{chunk['page_number']:<5} "
                f"{chunk['metadata']['char_count']:<12} "
                f"{len(chunk['text']):<12} "
                f"{chunk['metadata']['page_number']:<11} "
                f"{chunk['metadata']['source_file']:<30} "
                f"{status}"
            )

        # Unique ID check
        chunk_ids = [c["chunk_id"] for c in chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            msg = f"[{doc_name}] Duplicate chunk_ids detected!"
            global_errors.append(msg)
            print(f"\n  ✗ {msg}")
        else:
            print(f"\n  Unique chunk IDs : {len(chunk_ids)} / {len(chunk_ids)}  ✓")

    # ── GLOBAL SUMMARY ───────────────────────────────────────────────────────
    section("GLOBAL SUMMARY")
    print(f"  PDFs processed   : {len(pdf_paths)}")
    print(f"  Total chunks     : {total_chunks}")
    print(f"  Pipeline errors  : {len(global_errors)}")

    if global_errors:
        print("\n  ERRORS:")
        for e in global_errors:
            print(f"    ✗  {e}")
        print(f"\n  RESULT: PIPELINE FAILED — {len(global_errors)} error(s)")
        sys.exit(1)
    else:
        print(f"\n  {'═'*60}")
        print( "  RESULT: FULL END-TO-END PIPELINE PASSED — 0 ERRORS")
        print(f"  {'═'*60}")


if __name__ == "__main__":
    main()
