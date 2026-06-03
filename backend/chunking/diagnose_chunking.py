"""
Deep diagnostic script for the chunking module.
Evaluates: overlap correctness, metadata integrity, ID uniqueness, semantic continuity,
size bounds, and strategy differences.
"""

import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

sys.path.append(str(Path(__file__).parent))

from text_splitter import DocumentChunker

DIVIDER = "-" * 60

# ── Helper ────────────────────────────────────────────────────────────────────

def common_overlap(a: str, b: str) -> str:
    """Return the longest suffix of `a` that is also a prefix of `b`."""
    max_len = min(len(a), len(b))
    for length in range(max_len, 0, -1):
        if a.endswith(b[:length]):
            return b[:length]
    return ""

def similarity_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ── Fixtures ──────────────────────────────────────────────────────────────────

# Rich multi-paragraph document that exercises recursive splitting well
MOCK_DOC = {
    "doc_id": "70393f7539502291a2a2bb039d9f1b607885729a91e0ff5f046c8dc8b6b08e00",
    "source_file": "sample_invoice.pdf",
    "pages": [
        {
            "page_number": 1,
            "clean_text": (
                "BILL TO: Google Inc\n"
                "INVOICE Number: INV-2026-992\n"
                "Date: 2026-05-20\n"
                "Total Due: $1,250.00"
            ),
        },
        {
            "page_number": 2,
            "clean_text": (
                "Wednesday terms and conditions:\n"
                "Payment is due to IBM Corp within 30 days of the invoice date."
            ),
        },
    ],
}


def run_diagnostics():
    errors = []
    warnings = []

    # ── 1. PAGE-LEVEL STRATEGY ─────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  STRATEGY: PAGE-LEVEL")
    print(f"{'='*60}")

    page_chunker = DocumentChunker(strategy="page")
    page_chunks = page_chunker.chunk_document(MOCK_DOC)

    seen_ids = set()
    for chunk in page_chunks:
        print(f"\n{DIVIDER}")
        print(f"  chunk_id      : {chunk['chunk_id']}")
        print(f"  chunk_index   : {chunk['chunk_index']}")
        print(f"  page_number   : {chunk['page_number']}")
        print(f"  source_file   : {chunk['source_file']}")
        print(f"  char_count    : {chunk['metadata']['char_count']}")
        print(f"  text preview  : {repr(chunk['text'][:80])}")

        # ── Metadata integrity ─────────────────────────────────────────────
        if chunk["metadata"]["char_count"] != len(chunk["text"]):
            errors.append(f"[page] char_count mismatch on chunk {chunk['chunk_id']}")
        if chunk["metadata"]["page_number"] != chunk["page_number"]:
            errors.append(f"[page] page_number mismatch on chunk {chunk['chunk_id']}")
        if chunk["metadata"]["source_file"] != chunk["source_file"]:
            errors.append(f"[page] source_file mismatch on chunk {chunk['chunk_id']}")

        # ── ID uniqueness ──────────────────────────────────────────────────
        if chunk["chunk_id"] in seen_ids:
            errors.append(f"[page] Duplicate chunk_id: {chunk['chunk_id']}")
        seen_ids.add(chunk["chunk_id"])

    print(f"\n  Total page-level chunks : {len(page_chunks)}")
    expected_pages = len(MOCK_DOC["pages"])
    if len(page_chunks) != expected_pages:
        errors.append(f"[page] Expected {expected_pages} chunks, got {len(page_chunks)}")
    else:
        print(f"  Chunk count == page count ({expected_pages}) : PASS")

    # ── 2. RECURSIVE STRATEGY ──────────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("  STRATEGY: RECURSIVE CHARACTER (chunk_size=60, overlap=15)")
    print(f"{'='*60}")

    rec_chunker = DocumentChunker(strategy="recursive", chunk_size=60, chunk_overlap=15)
    rec_chunks = rec_chunker.chunk_document(MOCK_DOC)

    seen_ids_rec = set()
    size_violations = []
    overlap_pairs = []   # (chunk_i, chunk_i+1, overlap_str, overlap_len)

    for i, chunk in enumerate(rec_chunks):
        print(f"\n{DIVIDER}")
        print(f"  [{i}] chunk_id    : {chunk['chunk_id']}")
        print(f"  [{i}] chunk_index : {chunk['chunk_index']}")
        print(f"  [{i}] page_number : {chunk['page_number']}")
        print(f"  [{i}] char_count  : {chunk['metadata']['char_count']}")
        print(f"  [{i}] text        : {repr(chunk['text'])}")

        # ── Size bound ─────────────────────────────────────────────────────
        if len(chunk["text"]) > 60:
            size_violations.append(
                f"Chunk {chunk['chunk_id']} exceeds chunk_size: {len(chunk['text'])} chars"
            )
            errors.append(size_violations[-1])

        # ── Metadata integrity ─────────────────────────────────────────────
        if chunk["metadata"]["char_count"] != len(chunk["text"]):
            errors.append(f"[rec] char_count mismatch on chunk {chunk['chunk_id']}")
        if chunk["metadata"]["page_number"] != chunk["page_number"]:
            errors.append(f"[rec] page_number mismatch on chunk {chunk['chunk_id']}")
        if chunk["metadata"]["source_file"] != chunk["source_file"]:
            errors.append(f"[rec] source_file mismatch on chunk {chunk['chunk_id']}")

        # ── ID uniqueness ──────────────────────────────────────────────────
        if chunk["chunk_id"] in seen_ids_rec:
            errors.append(f"[rec] Duplicate chunk_id: {chunk['chunk_id']}")
        seen_ids_rec.add(chunk["chunk_id"])

        # ── Collect overlaps between adjacent same-page chunks ─────────────
        if i > 0 and rec_chunks[i - 1]["page_number"] == chunk["page_number"]:
            prev_text = rec_chunks[i - 1]["text"]
            curr_text = chunk["text"]
            overlap_str = common_overlap(prev_text, curr_text)
            overlap_pairs.append((i - 1, i, overlap_str, len(overlap_str)))

    # ── 3. OVERLAP ANALYSIS ────────────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("  OVERLAP ANALYSIS (adjacent same-page chunks)")
    print(f"{'='*60}")

    if not overlap_pairs:
        warnings.append("No adjacent same-page chunk pairs found – overlap analysis skipped.")
        print("  NOTE: No adjacent same-page pairs to analyse (small doc may not trigger overlap).")
    else:
        for (idx_a, idx_b, overlap_str, overlap_len) in overlap_pairs:
            print(f"\n  Chunks [{idx_a}] → [{idx_b}]:")
            print(f"    chunk[{idx_a}] text : {repr(rec_chunks[idx_a]['text'][-40:])}")
            print(f"    chunk[{idx_b}] text : {repr(rec_chunks[idx_b]['text'][:40])}")
            if overlap_str:
                print(f"    Shared suffix/prefix overlap : {repr(overlap_str)}")
                print(f"    Overlap length : {overlap_len} chars")
            else:
                print(f"    Shared token overlap : (word-boundary – check word token continuity)")
                # Check for word-level continuity via similarity of boundary tokens
                end_words = rec_chunks[idx_a]["text"].split()[-3:]
                start_words = rec_chunks[idx_b]["text"].split()[:3]
                shared = [w for w in end_words if w in start_words]
                if shared:
                    print(f"    Shared boundary words : {shared}")
                else:
                    print(f"    End words   : {end_words}")
                    print(f"    Start words : {start_words}")

    # ── 4. SEMANTIC CONTINUITY CHECK ──────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("  SEMANTIC CONTINUITY (adjacent chunk boundary similarity)")
    print(f"{'='*60}")

    for i in range(len(rec_chunks) - 1):
        a = rec_chunks[i]
        b = rec_chunks[i + 1]
        if a["page_number"] == b["page_number"]:
            # Similarity of a's last 30 chars vs b's first 30 chars
            ratio = similarity_ratio(a["text"][-30:], b["text"][:30])
            print(f"\n  [{i}]→[{i+1}] same page ({a['page_number']}) boundary similarity : {ratio:.2%}")
            print(f"    End   of [{i}] : {repr(a['text'][-30:])}")
            print(f"    Start of [{i+1}] : {repr(b['text'][:30])}")
        else:
            print(f"\n  [{i}]→[{i+1}] cross-page boundary (p{a['page_number']}→p{b['page_number']}) – continuity not expected")

    # ── 5. CHUNK ID UNIQUENESS SUMMARY ────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("  CHUNK ID UNIQUENESS SUMMARY")
    print(f"{'='*60}")
    total_ids = len(page_chunks) + len(rec_chunks)
    all_ids = list(seen_ids) + list(seen_ids_rec)
    unique_ids_across_runs = len(set(all_ids))
    print(f"  Page-level  chunks : {len(page_chunks)} | Unique IDs : {len(seen_ids)}")
    print(f"  Recursive   chunks : {len(rec_chunks)} | Unique IDs : {len(seen_ids_rec)}")
    print(f"  (Note: IDs reset per document; cross-strategy overlap is expected since same doc_id)")

    # ── 6. METADATA INTEGRITY TABLE ───────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("  METADATA INTEGRITY TABLE (recursive strategy)")
    print(f"{'='*60}")
    print(f"  {'Index':<6} {'Page':<6} {'CharCount':<10} {'len(text)':<10} {'Match':<6} {'Source File'}")
    print(f"  {'-'*5:<6} {'-'*4:<6} {'-'*9:<10} {'-'*9:<10} {'-'*5:<6} {'-'*25}")
    for chunk in rec_chunks:
        count_match = chunk["metadata"]["char_count"] == len(chunk["text"])
        print(
            f"  {chunk['chunk_index']:<6} "
            f"{chunk['page_number']:<6} "
            f"{chunk['metadata']['char_count']:<10} "
            f"{len(chunk['text']):<10} "
            f"{'✓' if count_match else '✗ MISMATCH':<6} "
            f"{chunk['metadata']['source_file']}"
        )

    # ── 7. FINAL REPORT ────────────────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("  FINAL DIAGNOSTIC REPORT")
    print(f"{'='*60}")

    if warnings:
        print("\n  WARNINGS:")
        for w in warnings:
            print(f"    ⚠  {w}")

    if errors:
        print("\n  ERRORS DETECTED:")
        for e in errors:
            print(f"    ✗  {e}")
        print(f"\n  {'='*60}")
        print("  RESULT: FAILED — see errors above")
        print(f"  {'='*60}")
        sys.exit(1)
    else:
        print("\n  Errors   : 0")
        print("  Warnings : " + str(len(warnings)))
        print(f"\n  {'='*60}")
        print("  RESULT: ALL DIAGNOSTICS PASSED")
        print(f"  {'='*60}")


if __name__ == "__main__":
    run_diagnostics()
