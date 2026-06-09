import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Compiled patterns ─────────────────────────────────────────────────────────
STEP_LABEL_PATTERN = re.compile(r'^\s*(?:Step|STEP|Stage|STAGE|Phase|PHASE)\s*(\d+)\b', re.IGNORECASE)
STEP_NUM_PATTERN   = re.compile(r'^\s*(\d+(?:\.\d+)+|\d+\.)\s*(.*)$')
BULLET_PATTERN     = re.compile(r'^\s*(?:[•\-*➕])\s*(.*)$')

# Sentence boundary split (used for minimal span extraction)
_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')

# ── Structural noise patterns (factual span sanitization) ─────────────────────
# Each pattern matches a line/fragment that is pure structural metadata and
# carries NO standalone factual meaning.  Order matters — more specific first.
_STRUCTURAL_NOISE_PATTERNS: List[re.Pattern] = []  # populated after class def

# Compiled inline for readability; stored in module-level list below.
_STRUCTURAL_NOISE_RAW = [
    # ── Workflow / document title lines ──────────────────────────────────────
    r'^(?:Add\s+Delivery\s+Location\s+(?:Process|User\s+Manual))',
    r'^(?:User\s+Manual\s+(?:for|of)\b)',
    r'^(?:Supplier\s+Registration\s+Portal)',
    r'^(?:Vendor\s+[Oo]nboarding\b)',
    r'^(?:New\s+Merchandise\b)',
    r'^(?:(?:Registration|Onboarding|Setup)\s+(?:Manual|Guide|Process|Flow|Workflow))\b',
    # ── Section heading / step label lines ───────────────────────────────────
    r'^(?:Step|STEP|Stage|STAGE|Phase|PHASE)\s*\d+\s*(?::|–|-|\.|$)',
    r'^(?:Section|SECTION)\s*\d+',
    r'^[A-Z][\w\s]{0,40}(?:Details|Process|Overview|Instructions|Summary|Guidelines)\s*$',
    # ── Pure numbering / sub-numbering prefixes ───────────────────────────────
    # e.g.  "5.4."  "3.1.2"  "A."  "A.1" standing alone
    r'^[A-Z]?\.?\s*\d+(?:\.\d+){1,3}\.?\s*$',
    # ── Table-of-contents entries ("Step N: Title") ───────────────────────────
    r'^(?:Step|Stage|Phase)\s*\d+\s*:\s*[A-Z][\w\s,/()–-]{1,80}$',
    # ── Page / footer noise (belt-and-suspenders; is_noise_line also catches) ─
    r'^\d+\s*\|\s*[Pp]\s*[Aa]\s*[Gg]\s*[Ee]',
    r'^[Pp]age\s+\d+',
    r'^STRICTLY\s+FOR\s+INTERNAL',
]

# Fragment patterns: lines that START with a structural prefix followed by
# substantive text.  Group 1 captures the trailing substantive content.
_STRUCTURAL_PREFIX_STRIP = re.compile(
    r'^(?:'
    r'(?:(?:Step|STEP|Stage|Phase)\s*\d+(?:\.\d+)*\s*(?::|–|-|—)?\s*)'
    r'|(?:[A-Z]?\.?\s*\d+(?:\.\d+){1,3}\.?\s*)'
    r'|(?:[A-Z]\.\s*)'
    r')',
    re.IGNORECASE,
)

# Incomplete-sentence guard: a line is considered a dangling fragment if it
# ends mid-word or is a bare noun phrase with no verb signal.
_DANGLING_FRAGMENT_PATTERN = re.compile(
    r'^(?:[A-Z][\w\s]{0,30})$'  # very short ALL-title-case with no punctuation
)

# Compile the raw strings into re.Pattern objects now that all helpers are ready
_STRUCTURAL_NOISE_PATTERNS.extend(
    re.compile(raw, re.IGNORECASE) for raw in _STRUCTURAL_NOISE_RAW
)

# ── Query granularity keyword sets ───────────────────────────────────────────
# Ordered from most-specific to least-specific; first match wins.
_WORKFLOW_KEYWORDS = [
    "registration flow", "onboarding flow", "onboarding process",
    "end-to-end", "end to end", "full process", "full workflow",
]
_PROCEDURAL_KEYWORDS = [
    "what are the steps", "list the steps", "steps to", "steps for",
    "how do i", "how to", "process for", "process to",
    "procedure for", "procedure to", "walk me through",
    "guide me", "guide to", "workflow for", "workflow to",
    "how can i", "how should i register", "how should i add",
    "how should i create", "how should i submit",
    "registration process", "onboarding steps",
]
_EXPLANATORY_KEYWORDS = [
    "what is", "what are", "define ", "explain ", "describe ",
    "tell me about", "meaning of", "definition of",
    "what does", "what do",
]
# Factual is the default when none of the above match, but these signal it:
_FACTUAL_SIGNALS = [
    "where is", "which link", "what link", "what url", "portal link",
    "how should i declare", "what format", "what is the format",
    "what is the rule", "what is the limit", "should i declare",
    "how should i", "how do i declare", "what is the gstin",
    "what is the pan", "what is the fssai",
]


def classify_query_granularity(query: str) -> str:
    """
    Classifies a query into one of four granularity levels:
      - 'workflow'     : end-to-end full-pipeline queries
      - 'procedural'   : step-by-step how-to queries
      - 'explanatory'  : definition / description queries
      - 'factual'      : short precise fact queries (default)

    Decision is purely keyword-driven — no ML inference.
    """
    q = query.lower().strip()

    for kw in _WORKFLOW_KEYWORDS:
        if kw in q:
            logger.info(f"Query granularity: workflow (matched '{kw}')")
            return "workflow"

    for kw in _PROCEDURAL_KEYWORDS:
        if kw in q:
            logger.info(f"Query granularity: procedural (matched '{kw}')")
            return "procedural"

    for kw in _FACTUAL_SIGNALS:
        if kw in q:
            logger.info(f"Query granularity: factual (matched factual signal '{kw}')")
            return "factual"

    for kw in _EXPLANATORY_KEYWORDS:
        if kw in q:
            logger.info(f"Query granularity: explanatory (matched '{kw}')")
            return "explanatory"

    logger.info("Query granularity: factual (default — no keyword matched)")
    return "factual"


# ── Noise filtering ───────────────────────────────────────────────────────────

def is_noise_line(line: str) -> bool:
    line_lower = line.strip().lower()
    if not line_lower:
        return True
    if "strictly for internal circulation only" in line_lower:
        return True
    if re.search(r'\b\d+\s*\|\s*p\s*a\s*g\s*e\b', line_lower):
        return True
    if re.search(r'\bpage\s*\d+\s*(?:of)?\s*\d*\b', line_lower):
        return True
    if re.match(r'^[-_=*#\s\d|]+$', line_lower) and len(line_lower) > 3:
        if not re.match(r'^\d+\.?$', line_lower):
            return True
    return False


def reconstruct_lines(text: str) -> List[str]:
    raw_lines = [l.strip() for l in text.split('\n') if l.strip()]
    merged_lines: List[str] = []

    for line in raw_lines:
        if not merged_lines:
            merged_lines.append(line)
            continue

        prev = merged_lines[-1]
        is_url = line.startswith(("http://", "https://", "tips://", "www.")) or "fssai.gov.in" in line
        prev_ends_url = (
            prev.endswith((".com", ".in", ".gov", ".org", ".com/", ".in/", "/"))
            and ("http" in prev or "tips" in prev)
        )
        ends_with_punc = prev.endswith(('.', '!', '?', ':', '>', '➕', '•', '-', '*'))
        starts_with_step = (
            STEP_LABEL_PATTERN.match(line)
            or STEP_NUM_PATTERN.match(line)
            or BULLET_PATTERN.match(line)
        )

        if not ends_with_punc and not starts_with_step and not is_url and not prev_ends_url and len(prev) > 0:
            merged_lines[-1] = re.sub(r'\s+', ' ', prev + " " + line)
        else:
            merged_lines.append(line)

    return merged_lines


# ── Main class ────────────────────────────────────────────────────────────────

class ContextAssembler:
    """
    Scope-aware grounded answer assembler.

    For PROCEDURAL / WORKFLOW queries   → full multi-chunk workflow reconstruction.
    For FACTUAL / EXPLANATORY queries   → minimal single-span answer extraction
                                          from the top-scoring chunk only.
                                          No workflow sections, no neighboring steps,
                                          no completeness warnings.
    """

    def __init__(self) -> None:
        logger.info("ContextAssembler initialized.")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_chunk_index(self, chunk: Dict[str, Any]) -> int:
        meta = chunk.get("metadata", {})
        idx = meta.get("chunk_index") or chunk.get("chunk_index")
        if idx is not None:
            return int(idx)
        chunk_id = chunk.get("chunk_id", "")
        match = re.search(r'_c(\d+)$', chunk_id)
        return int(match.group(1)) if match else 0

    def _get_page_number(self, chunk: Dict[str, Any]) -> int:
        meta = chunk.get("metadata", {})
        return meta.get("page_number") or chunk.get("page_number") or 0

    def _get_page_order(self, chunk: Dict[str, Any]) -> int:
        meta = chunk.get("metadata", {})
        return meta.get("page_order") or chunk.get("page_order") or 0

    # ── Factual: minimal answer span extraction ───────────────────────────────

    # ── Factual span sanitization ─────────────────────────────────────────────

    def _sanitize_factual_span(self, text: str) -> str:
        """
        Strips structural procedural noise from a candidate answer span.

        Removes:
          • workflow / document title lines
          • section headings and step labels
          • pure numbering prefixes (standalone or as line prefixes)
          • procedural continuation fragments with no semantic value

        Preserves:
          • verbatim content of every sentence that survives filtering
          • grammatical correctness (no word-splicing or rewriting)

        This method NEVER paraphrases or rewrites meaning — it is a structural
        filter only.  If nothing survives filtering the original text is returned
        unchanged so we never return an empty answer.
        """
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        cleaned: List[str] = []

        for line in lines:
            # 1. Hard-reject lines that are pure structural noise
            is_noise = False
            for pat in _STRUCTURAL_NOISE_PATTERNS:
                if pat.match(line):
                    is_noise = True
                    break
            if is_noise:
                logger.debug(f"Sanitize: dropped noise line: '{line[:60]}'")
                continue

            # 2. Strip structural prefix from lines that START with one but
            #    also contain substantive trailing content.
            stripped = _STRUCTURAL_PREFIX_STRIP.sub('', line).strip()

            # If stripping consumed everything meaningful, drop the line.
            if not stripped:
                logger.debug(f"Sanitize: dropped fully-prefixed line: '{line[:60]}'")
                continue

            # 3. Drop very short dangling fragments (e.g. bare "5.4." residue
            #    after prefix removal, or orphaned title-case noun phrases).
            if len(stripped) < 10 and re.match(r'^[\d.]+$', stripped):
                logger.debug(f"Sanitize: dropped numeric residue: '{stripped}'")
                continue

            cleaned.append(stripped)

        if not cleaned:
            # Nothing survived — return the original rather than an empty answer.
            logger.warning("Sanitize: all lines were structural; returning original text.")
            return text.strip()

        # Re-join and collapse extra whitespace
        result = ' '.join(cleaned).strip()
        result = re.sub(r'  +', ' ', result)
        return result

    def extract_minimal_answer_span(
        self,
        query: str,
        top_chunk: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extracts the smallest semantically complete grounded sentence(s) from
        the top-scoring chunk that are most likely to directly answer the query.

        Strategy:
          1. Split the chunk text into individual sentences.
          2. Score each sentence by non-stop-word overlap with the query.
          3. Return the highest-scoring sentence(s) — capped at 3 to keep the
             answer concise.  Falls back to the raw answer_excerpt if scoring
             yields nothing useful.

        NEVER paraphrases, infers, or invents content — output is verbatim.
        """
        text = top_chunk.get("text", top_chunk.get("answer_excerpt", ""))
        page_num = self._get_page_number(top_chunk)
        source_file = (
            top_chunk.get("metadata", {}).get("source_file")
            or top_chunk.get("source_file", "")
        )

        # Stopwords to ignore during overlap scoring
        _STOP = {
            "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
            "to", "for", "in", "on", "at", "of", "with", "that", "this",
            "it", "its", "i", "my", "should", "how", "what", "which", "do",
            "does", "did", "be", "been", "being", "have", "has", "had",
            "will", "would", "can", "could", "may", "might",
        }

        q_tokens = set(
            t.lower() for t in re.findall(r'\b\w+\b', query)
            if t.lower() not in _STOP and len(t) > 2
        )

        # Split into sentences — try period-based split first, fall back to lines
        raw_sentences = _SENT_SPLIT.split(text.strip())
        if len(raw_sentences) < 2:
            raw_sentences = [l.strip() for l in text.split('\n') if l.strip()]

        # Filter noise
        sentences = [s for s in raw_sentences if s.strip() and not is_noise_line(s)]

        if not sentences:
            # Nothing left after filtering — return the raw excerpt
            return {
                "minimal_answer": top_chunk.get("answer_excerpt", text).strip(),
                "page_number": page_num,
                "source_file": source_file,
            }

        # Score each sentence
        scored: List[Tuple[float, int, str]] = []
        for idx, sent in enumerate(sentences):
            s_tokens = set(
                t.lower() for t in re.findall(r'\b\w+\b', sent)
                if t.lower() not in _STOP and len(t) > 2
            )
            overlap = len(q_tokens & s_tokens) / max(len(q_tokens), 1)
            scored.append((overlap, idx, sent))

        # Sort by score desc, break ties by original position
        scored.sort(key=lambda x: (-x[0], x[1]))

        # Pick top sentences (cap at 3), then restore original reading order
        top_n = min(3, len(scored))
        # Only include if they actually overlap with the query
        best = [item for item in scored[:top_n] if item[0] > 0.0]
        if not best:
            # Zero overlap → return the single highest-scoring sentence
            best = [scored[0]]

        best_sorted = sorted(best, key=lambda x: x[1])  # restore reading order
        minimal_answer = " ".join(s for _, _, s in best_sorted).strip()

        logger.info(
            f"Minimal span extracted ({len(best_sorted)} sentence(s), "
            f"top overlap={best_sorted[0][0]:.2f}): '{minimal_answer[:80]}...'"
        )

        # ── Factual Span Sanitization ─────────────────────────────────────────
        # Strip structural/procedural metadata (workflow titles, step labels,
        # numbering prefixes) from the span.  Verbatim text is never rewritten.
        sanitized = self._sanitize_factual_span(minimal_answer)
        if sanitized != minimal_answer:
            logger.info(
                f"Sanitized factual span: '{sanitized[:100]}'"
            )

        return {
            "minimal_answer": sanitized,
            "page_number": page_num,
            "source_file": source_file,
        }

    # ── Procedural/Workflow: full multi-chunk assembly ─────────────────────────

    def group_chunks(
        self, chunks: List[Dict[str, Any]]
    ) -> List[Tuple[Tuple[str, str], List[Dict[str, Any]]]]:
        """
        Groups candidate chunks by (source_file, procedure_id/section_title).
        Returns groups sorted by the highest candidate score in each group.
        """
        groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            proc_id    = meta.get("procedure_id")  or chunk.get("procedure_id")  or ""
            sec_title  = meta.get("section_title") or chunk.get("section_title") or ""
            source_file = meta.get("source_file")  or chunk.get("source_file")   or ""

            if proc_id:
                key = (source_file, f"proc_{proc_id}")
            elif sec_title:
                key = (source_file, f"sec_{sec_title}")
            else:
                key = (source_file, "general")

            groups.setdefault(key, []).append(chunk)

        for key in groups:
            groups[key].sort(
                key=lambda c: (
                    self._get_page_number(c),
                    self._get_page_order(c),
                    self._get_chunk_index(c),
                )
            )

        return sorted(
            groups.items(),
            key=lambda item: max(c.get("score", 0.0) for c in item[1]),
            reverse=True,
        )

    def extract_steps_from_group(
        self, sorted_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Reconstructs ordered steps across chunks, deduplicating overlap windows.
        """
        raw_steps: List[Dict[str, Any]] = []
        seen_normalized: Set[str] = set()

        for chunk in sorted_chunks:
            text = chunk.get("text", chunk.get("answer_excerpt", ""))
            page_num    = self._get_page_number(chunk)
            source_file = chunk.get("metadata", {}).get("source_file", chunk.get("source_file", ""))

            for line in reconstruct_lines(text):
                if is_noise_line(line):
                    continue
                norm = "".join(line.lower().split())
                if norm in seen_normalized:
                    continue
                seen_normalized.add(norm)

                step_num: Optional[int] = None
                m = STEP_LABEL_PATTERN.match(line)
                if m:
                    step_num = int(m.group(1))
                else:
                    m2 = STEP_NUM_PATTERN.match(line)
                    if m2:
                        try:
                            step_num = int(m2.group(1).split('.')[0])
                        except ValueError:
                            pass

                raw_steps.append({
                    "text": line,
                    "page_number": page_num,
                    "source_file": source_file,
                    "step_number": step_num,
                })

        return raw_steps

    def validate_continuity(
        self,
        sorted_chunks: List[Dict[str, Any]],
        steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluates sequence continuity and identifies gaps or missing steps."""
        chunk_indices    = [self._get_chunk_index(c) for c in sorted_chunks]
        step_numbers     = [s["step_number"] for s in steps if s["step_number"] is not None]
        unique_step_nums = sorted(set(step_numbers))

        index_completeness = 1.0
        if len(chunk_indices) > 1:
            span = max(chunk_indices) - min(chunk_indices) + 1
            index_completeness = len(set(chunk_indices)) / span

        step_completeness = 1.0
        if len(unique_step_nums) > 1:
            span = max(unique_step_nums) - min(unique_step_nums) + 1
            step_completeness = len(unique_step_nums) / span

        workflow_completeness = min(index_completeness, step_completeness)

        index_continuity = 1.0
        if len(chunk_indices) > 1:
            contiguous = sum(
                1 for i in range(len(chunk_indices) - 1)
                if chunk_indices[i + 1] - chunk_indices[i] == 1
            )
            index_continuity = contiguous / (len(chunk_indices) - 1)

        step_continuity = 1.0
        if len(unique_step_nums) > 1:
            contiguous = sum(
                1 for i in range(len(unique_step_nums) - 1)
                if unique_step_nums[i + 1] - unique_step_nums[i] == 1
            )
            step_continuity = contiguous / (len(unique_step_nums) - 1)

        procedural_continuity = (index_continuity + step_continuity) / 2.0

        missing_steps: List[int] = []
        if len(unique_step_nums) > 1:
            full_set = set(range(min(unique_step_nums), max(unique_step_nums) + 1))
            missing_steps = sorted(full_set - set(unique_step_nums))

        missing_chunks: List[int] = []
        if len(chunk_indices) > 1:
            full_set = set(range(min(chunk_indices), max(chunk_indices) + 1))
            missing_chunks = sorted(full_set - set(chunk_indices))

        return {
            "completeness_score": float(workflow_completeness),
            "continuity_score":   float(procedural_continuity),
            "missing_steps":      missing_steps,
            "missing_chunks":     missing_chunks,
        }

    # ── Public entry point ────────────────────────────────────────────────────

    def assemble(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        query_granularity: str = "procedural",
    ) -> Dict[str, Any]:
        """
        Scope-aware assembly entry point.

        Parameters
        ----------
        query              : original corrected query string
        candidates         : ranked candidate chunk dicts
        query_granularity  : one of 'factual' | 'explanatory' | 'procedural' | 'workflow'

        Returns
        -------
        Assembly result dict.  Schema is the same for all granularity levels so
        that the orchestrator can consume it uniformly.
        """
        _empty = {
            "assembled_context":   "",
            "ordered_steps":       [],
            "completeness_metadata": {
                "completeness_score": 1.0,
                "continuity_score":   1.0,
                "missing_steps":      [],
                "missing_chunks":     [],
            },
            "continuity_score":       1.0,
            "missing_step_indicators": [],
            "granularity":            query_granularity,
        }

        if not candidates:
            return _empty

        # ── FACTUAL / EXPLANATORY: minimal span from top chunk only ───────────
        if query_granularity in ("factual", "explanatory"):
            top_chunk = candidates[0]
            span = self.extract_minimal_answer_span(query, top_chunk)
            return {
                "assembled_context":   span["minimal_answer"],
                "ordered_steps":       [
                    {
                        "text":        span["minimal_answer"],
                        "page_number": span["page_number"],
                        "source_file": span["source_file"],
                        "step_number": None,
                    }
                ],
                "completeness_metadata": {
                    "completeness_score": 1.0,
                    "continuity_score":   1.0,
                    "missing_steps":      [],
                    "missing_chunks":     [],
                },
                "continuity_score":        1.0,
                "missing_step_indicators": [],
                "granularity":             query_granularity,
            }

        # ── PROCEDURAL / WORKFLOW: full multi-chunk reconstruction ────────────
        grouped = self.group_chunks(candidates)
        if not grouped:
            return _empty

        primary_key, primary_chunks = grouped[0]
        logger.info(
            f"Assembling '{query_granularity}' context for group: {primary_key} "
            f"({len(primary_chunks)} chunks)"
        )

        ordered_steps     = self.extract_steps_from_group(primary_chunks)
        completeness_meta = self.validate_continuity(primary_chunks, ordered_steps)
        assembled_context = "\n".join(s["text"] for s in ordered_steps)

        return {
            "assembled_context":     assembled_context,
            "ordered_steps":         ordered_steps,
            "completeness_metadata": completeness_meta,
            "continuity_score":      completeness_meta["continuity_score"],
            "missing_step_indicators": completeness_meta["missing_steps"],
            "granularity":           query_granularity,
        }
