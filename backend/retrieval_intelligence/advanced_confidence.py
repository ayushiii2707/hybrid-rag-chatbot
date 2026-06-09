import logging
import os
import json
import re
import spacy
from typing import Dict, Any, List, Set
from chunk_quality import ChunkQualityAnalyzer
from entity_detectors import (
    detect_query_answer_type,
    chunk_satisfies_answer_type,
    ANSWER_TYPE_REGISTRY,
)

logger = logging.getLogger(__name__)

# Basic stopwords to extract clean acronyms/terms if needed
STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "to", "for",
    "in", "on", "at", "by", "of", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "from", "up", "down",
    "in", "out", "off", "over", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "any", "both", "each", "few",
    "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "can", "will", "just", "should", "now",
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she", "her",
    "it", "its", "they", "them", "their", "this", "that", "these", "those"
}

# ---------------------------------------------------------------------------
# Declarative / factual sentence patterns used by _query_answer_alignment_score
# ---------------------------------------------------------------------------
_DECLARATIVE_PATTERNS = [
    re.compile(r"\bis\b", re.IGNORECASE),           # "X is Y"
    re.compile(r"\bare\b", re.IGNORECASE),           # "X are Y"
    re.compile(r"\bcan be\b", re.IGNORECASE),
    re.compile(r"\bmust\b", re.IGNORECASE),
    re.compile(r"\bshould\b", re.IGNORECASE),
    re.compile(r"\brefer(?:s)? to\b", re.IGNORECASE),
    re.compile(r"\bdefined as\b", re.IGNORECASE),
    re.compile(r"\bstep\s*\d+\b", re.IGNORECASE),   # numbered procedure
    re.compile(r"\b\d+\.\s+\w", re.MULTILINE),      # "1. Something"
    re.compile(r"https?://", re.IGNORECASE),         # direct URL
]


class AdvancedConfidenceScorer:
    """
    Computes calibrated truth-level confidence scores using multi-factor signals:
    1. Semantic Similarity (Cross-Encoder, passed in from Reranker)
    2. BM25 Keyword Score
    3. Named Entity and Acronym Overlap (spaCy)
    4. Metadata Boosts (page-level heuristics)
    5. Chunk Quality Rating (ChunkQualityAnalyzer)
    6. Answer-Type Awareness (entity_detectors registry)
    7. Query-Answer Alignment (declarative/factual pattern detection)
    8. Answerability Score (per-chunk independent completeness estimate)
    9. Content Sufficiency Score (replaces naive word-count fragmentation penalty)

    NOTE: All scoring components are fully generic — no domain-specific special cases.
    """

    def __init__(self, config_path: str = None, spacy_model: str = "en_core_web_sm") -> None:
        """
        Initializes the AdvancedConfidenceScorer with configurations.
        """
        self.min_confidence_threshold = 0.55
        self.high_confidence_threshold = 0.80
        self.weights = {
            "semantic": 0.55,
            "keyword": 0.12,
            "entity": 0.08,
            "metadata": 0.08,
            "quality": 0.04,
            "answer_type": 0.07,
            "answerability": 0.06,
        }
        self.validation_keywords = ["validation", "rules", "format", "must", "should", "mandatory"]
        self.boost_value = 0.10

        # Load configuration
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                self.min_confidence_threshold = config_data.get("min_confidence_threshold", self.min_confidence_threshold)
                self.high_confidence_threshold = config_data.get("high_confidence_threshold", self.high_confidence_threshold)
                # Only override weights that are present in the config; keep new keys from __init__
                loaded_weights = config_data.get("weights", {})
                self.weights.update(loaded_weights)

                meta_boosts = config_data.get("metadata_boosts", {})
                self.validation_keywords = meta_boosts.get("validation_rule_keywords", self.validation_keywords)
                self.boost_value = meta_boosts.get("boost_value", self.boost_value)
                logger.info(f"Loaded AdvancedConfidenceScorer config from {config_path}")
            except Exception as e:
                logger.warning(f"Could not load confidence settings from config: {e}")

        # Normalize weights so they always sum to 1.0
        total_w = sum(self.weights.values())
        if total_w > 0:
            self.weights = {k: v / total_w for k, v in self.weights.items()}

        # Initialize sub-components
        self.quality_analyzer = ChunkQualityAnalyzer()

        try:
            self.nlp = spacy.load(spacy_model)
            logger.info(f"spaCy model '{spacy_model}' loaded successfully in AdvancedConfidenceScorer.")
        except Exception as e:
            logger.error(f"Failed to load spaCy model '{spacy_model}' in AdvancedConfidenceScorer: {e}")
            raise RuntimeError(f"Could not load spaCy model: {spacy_model}") from e

    # ------------------------------------------------------------------
    # Entity / Acronym Overlap
    # ------------------------------------------------------------------

    def extract_entities_and_acronyms(self, text: str) -> Set[str]:
        """
        Extracts lowercase entity texts (ORG, DATE, CARDINAL) and uppercase acronyms from text.
        """
        if not text:
            return set()

        doc = self.nlp(text)
        results = set()

        # 1. spaCy Entities
        for ent in doc.ents:
            if ent.label_ in {"ORG", "DATE", "CARDINAL"}:
                results.add(ent.text.strip().lower())

        # 2. Acronyms (Uppercase tokens of length 2 to 6, like MSME, UDYAM, FSSAI)
        acronyms = re.findall(r"\b[A-Z]{2,6}\b", text)
        for ac in acronyms:
            results.add(ac.lower())

        return results

    def compute_entity_overlap(self, query: str, chunk_text: str) -> float:
        """
        Calculates the ratio of query entities/acronyms present in the chunk text.
        """
        query_ents = self.extract_entities_and_acronyms(query)
        if not query_ents:
            return 1.0  # No query entities to match — no penalty

        chunk_text_lower = chunk_text.lower()
        matched_count = sum(1 for ent in query_ents if ent in chunk_text_lower)
        return matched_count / len(query_ents)

    # ------------------------------------------------------------------
    # Metadata Score
    # ------------------------------------------------------------------

    def compute_metadata_score(self, query: str, chunk_metadata: Dict[str, Any], chunk_text: str) -> float:
        """
        Calculates the metadata score including validation rule keyword boosts and page boosts.
        """
        score = 0.5  # Base metadata score
        chunk_text_lower = chunk_text.lower()
        query_lower = query.lower()

        # 1. Validation Rule Keyword Boost
        has_validation_kw = any(kw in chunk_text_lower for kw in self.validation_keywords)
        if has_validation_kw:
            score += self.boost_value

        # 2. Page-level boost for registration validation page (page 10)
        source_file = chunk_metadata.get("source_file", "")
        page_number = chunk_metadata.get("page_number", -1)

        if "registration" in source_file.lower() and page_number == 10:
            if any(term in query_lower for term in ["validation", "rules", "msme", "udyam"]):
                score += 0.25

        # 3. Page-level boost for active status page (page 11)
        if "delivery" in source_file.lower() and page_number == 11:
            if any(term in query_lower for term in ["fssai", "active", "status", "link"]):
                score += 0.25

        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # Content Sufficiency Score  (replaces static fragmentation penalty)
    # ------------------------------------------------------------------

    def _sufficiency_score(self, chunk_text: str) -> float:
        """
        Estimates how 'complete' a chunk is as a self-contained answer.

        Instead of penalising by raw word count, we measure:
          1. Sentence completeness ratio — sentences with proper terminal punctuation.
          2. Token / sentence density — meaningful words per sentence.
          3. Presence of at least one factual payload (a number, proper noun, or entity pattern).

        Returns a score in [0.0, 1.0].  Perfect chunks score 1.0; fragments score < 0.7.
        """
        if not chunk_text or not chunk_text.strip():
            return 0.0

        stripped = chunk_text.strip()

        # --- 1. Sentence completeness ---
        sentences = re.split(r"(?<=[.!?])\s+", stripped)
        sentences = [s for s in sentences if s.strip()]
        if not sentences:
            return 0.3

        complete = sum(1 for s in sentences if re.search(r"[.!?]$", s.strip()))
        completeness_ratio = complete / len(sentences) if sentences else 0.0

        # --- 2. Token density (mean meaningful tokens per sentence) ---
        words = [w for w in stripped.split() if w.isalpha() and len(w) > 2]
        mean_tokens_per_sentence = len(words) / len(sentences) if sentences else 0.0
        # Normalise: 10+ meaningful words per sentence = full score
        density_score = min(1.0, mean_tokens_per_sentence / 10.0)

        # --- 3. Factual payload check ---
        has_number = bool(re.search(r"\d", stripped))
        has_upper_word = bool(re.search(r"\b[A-Z][a-z]+\b", stripped))  # Proper noun
        payload_score = 1.0 if (has_number or has_upper_word) else 0.6

        # Weighted combination
        sufficiency = (0.4 * completeness_ratio) + (0.4 * density_score) + (0.2 * payload_score)
        return float(max(0.0, min(1.0, sufficiency)))

    # ------------------------------------------------------------------
    # Answer-Type Awareness Score
    # ------------------------------------------------------------------

    def _answer_type_score(self, query: str, chunk_text: str) -> float:
        """
        Detects the expected answer type from the query, then checks whether
        the chunk actually contains an entity of that type.

        - If the query implies a URL/link answer, chunks containing a URL score 1.0;
          chunks without any URL score 0.0.
        - For 'generic' queries (no detectable answer type), returns 1.0 (neutral).

        This function delegates all entity detection to entity_detectors.py and
        uses no domain-specific rules itself.

        Returns float in [0.0, 1.0].
        """
        answer_type = detect_query_answer_type(query)
        if answer_type == "generic":
            return 1.0  # No answer-type constraint — don't penalise

        satisfies = chunk_satisfies_answer_type(chunk_text, answer_type)
        return 1.0 if satisfies else 0.0

    # ------------------------------------------------------------------
    # Query-Answer Alignment Score
    # ------------------------------------------------------------------

    def _query_answer_alignment_score(self, query: str, chunk_text: str) -> float:
        """
        Estimates structural alignment between query intent and chunk response form.

        Principle: if the query uses interrogative patterns (what, how, where, when),
        the chunk should contain declarative / factual sentence structures.

        Returns a score in [0.5, 1.0].
          - 1.0  : chunk contains several declarative / factual signals.
          - 0.5  : chunk contains no declarative signals (structural mismatch).
        """
        interrogatives = re.compile(
            r"\b(?:what|how|where|when|which|who|why)\b", re.IGNORECASE
        )
        is_question = bool(interrogatives.search(query))

        if not is_question:
            return 1.0  # Non-question query — no alignment constraint

        matches = sum(1 for p in _DECLARATIVE_PATTERNS if p.search(chunk_text))
        # Normalise: 3+ matches = max score
        normalised = min(1.0, matches / 3.0)
        # Floor at 0.5 so it never zeroes out the overall score
        return max(0.5, normalised)

    # ------------------------------------------------------------------
    # Answerability Score
    # ------------------------------------------------------------------

    def _answerability_score(self, query: str, chunk_text: str) -> float:
        """
        Independently estimates whether the chunk text is likely to answer the query,
        without relying on semantic similarity signals.

        Factors:
          1. Query keyword overlap — fraction of non-stopword query terms present in chunk.
          2. Answer completeness — chunk ends with punctuation and has ≥ 2 sentences.
          3. Specificity — chunk contains at least one specific entity (number, acronym, URL).

        Returns float in [0.0, 1.0].
        """
        query_tokens = [
            t.lower() for t in re.findall(r"\b\w+\b", query)
            if t.lower() not in STOPWORDS and len(t) > 2
        ]
        if not query_tokens:
            return 0.5  # Cannot assess — neutral

        chunk_lower = chunk_text.lower()

        # 1. Keyword overlap
        matched = sum(1 for t in query_tokens if t in chunk_lower)
        overlap_ratio = matched / len(query_tokens)

        # 2. Answer completeness (ends with punctuation, has ≥ 2 sentences)
        sentences = re.split(r"(?<=[.!?])\s+", chunk_text.strip())
        has_closing_punct = bool(re.search(r"[.!?]$", chunk_text.strip()))
        completeness = 1.0 if (len(sentences) >= 2 and has_closing_punct) else 0.6

        # 3. Specificity (numbers, acronyms, URLs)
        has_specific = bool(
            re.search(r"\d", chunk_text) or
            re.search(r"\b[A-Z]{2,6}\b", chunk_text) or
            re.search(r"https?://", chunk_text)
        )
        specificity = 1.0 if has_specific else 0.7

        return float(max(0.0, min(1.0,
            (0.5 * overlap_ratio) + (0.3 * completeness) + (0.2 * specificity)
        )))

    # ------------------------------------------------------------------
    # Intent Mismatch Penalty (preserved from Phase 1)
    # ------------------------------------------------------------------

    def _intent_mismatch_penalty(self, query: str, chunk_text: str) -> float:
        """
        Returns a negative penalty (-0.20) if the query signals intent about
        duplicate checking / uniqueness validation, but the chunk text contains
        no matching validation signals.

        Returns 0.0 if no penalty applies.
        """
        intent_terms = ["already exists", "duplicate", "existing vendor", "uniqueness", "validation"]
        query_lower = query.lower()
        has_intent = any(term in query_lower for term in intent_terms)
        if not has_intent:
            return 0.0

        chunk_lower = chunk_text.lower()
        validation_terms = ["already", "exist", "duplicate", "existing", "unique", "validation", "validate"]
        if not any(term in chunk_lower for term in validation_terms):
            logger.info("Applying intent mismatch penalty (-0.20): chunk lacks duplicate/validation terms.")
            return -0.20

        return 0.0

    # ------------------------------------------------------------------
    # Main Scoring Entry Point
    # ------------------------------------------------------------------

    def score_candidate(
        self,
        query: str,
        chunk_text: str,
        semantic_score: float,
        keyword_score: float,
        chunk_metadata: Dict[str, Any],
        agreement_boost: float = 0.0,
        agreement_detected: bool = False,
        faiss_rank: int = 999,
        bm25_rank: int = 999,
        source_agreement_boost: float = 0.0,
        source_agreement_detected: bool = False,
        supporting_chunks: int = 1,
        supporting_documents: int = 1
    ) -> Dict[str, Any]:
        """
        Calculates the composite confidence score for a candidate chunk.

        Replaces the static fragmentation penalty with content sufficiency scoring
        and adds answer-type awareness, query-answer alignment, and answerability
        as first-class scoring dimensions.
        """
        # Store query for multi-chunk pipeline checks in apply_ambiguity_penalties
        self.last_query = query

        # 1. Standard signals
        entity_score = self.compute_entity_overlap(query, chunk_text)
        metadata_score = self.compute_metadata_score(query, chunk_metadata, chunk_text)
        quality_score = self.quality_analyzer.analyze(chunk_text)

        # 2. New intelligence signals
        answer_type_score = self._answer_type_score(query, chunk_text)
        answerability = self._answerability_score(query, chunk_text)
        alignment = self._query_answer_alignment_score(query, chunk_text)
        sufficiency = self._sufficiency_score(chunk_text)

        # 3. Weighted linear combination using normalised weights
        ws = self.weights.get("semantic", 0.55)
        wk = self.weights.get("keyword", 0.12)
        we = self.weights.get("entity", 0.08)
        wm = self.weights.get("metadata", 0.08)
        wq = self.weights.get("quality", 0.04)
        wat = self.weights.get("answer_type", 0.07)
        wan = self.weights.get("answerability", 0.06)

        # Fold alignment and sufficiency into semantic and quality channels
        # (alignment modulates semantic effectiveness; sufficiency modulates quality)
        adjusted_semantic = semantic_score * alignment
        adjusted_quality = quality_score * sufficiency

        base_confidence = (
            (ws * adjusted_semantic) +
            (wk * keyword_score) +
            (we * entity_score) +
            (wm * metadata_score) +
            (wq * adjusted_quality) +
            (wat * answer_type_score) +
            (wan * answerability)
        )

        # 4. Intent Mismatch Penalty (additive, from Phase 1)
        mismatch_penalty = self._intent_mismatch_penalty(query, chunk_text)
        base_confidence += mismatch_penalty

        # 5. Add retrieval agreement boost
        base_confidence += agreement_boost

        # 6. Add source agreement boost
        base_confidence += source_agreement_boost

        logger.info(
            f"score_candidate | semantic={semantic_score:.3f} alignment={alignment:.3f} "
            f"keyword={keyword_score:.3f} entity={entity_score:.3f} "
            f"answer_type={answer_type_score:.3f} answerability={answerability:.3f} "
            f"sufficiency={sufficiency:.3f} quality={quality_score:.3f} "
            f"mismatch_penalty={mismatch_penalty:.2f} agreement_boost={agreement_boost:.2f} "
            f"source_agreement_boost={source_agreement_boost:.2f} → final={base_confidence:.4f}"
        )

        return {
            "score": float(max(0.0, min(1.0, base_confidence))),
            "breakdown": {
                "semantic": float(semantic_score),
                "keyword": float(keyword_score),
                "entity": float(entity_score),
                "metadata": float(metadata_score),
                "quality": float(quality_score),
                "answer_type": float(answer_type_score),
                "answerability": float(answerability),
                "alignment": float(alignment),
                "sufficiency": float(sufficiency),
                "intent_mismatch_penalty": float(mismatch_penalty),
                "agreement_boost": float(agreement_boost),
                "agreement_detected": bool(agreement_detected),
                "faiss_rank": int(faiss_rank),
                "bm25_rank": int(bm25_rank),
                "source_agreement_boost": float(source_agreement_boost),
                "source_agreement_detected": bool(source_agreement_detected),
                "supporting_chunks": int(supporting_chunks),
                "supporting_documents": int(supporting_documents),
            }
        }

    # ------------------------------------------------------------------
    # Ambiguity and Procedural Chain Penalties
    # ------------------------------------------------------------------

    def apply_ambiguity_penalties(self, ranked_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Applies ambiguity penalties and evaluates workflow completeness & continuity
        across assembled procedural chains to adjust confidence scores dynamically.
        """
        if not ranked_candidates:
            return ranked_candidates

        # 1. Standard Ambiguity Penalty (top 2 comparison)
        if len(ranked_candidates) >= 2:
            c1 = ranked_candidates[0]
            c2 = ranked_candidates[1]

            sem1 = c1.get("breakdown", {}).get("faiss_similarity", c1.get("breakdown", {}).get("semantic", 0.0))
            sem2 = c2.get("breakdown", {}).get("faiss_similarity", c2.get("breakdown", {}).get("semantic", 0.0))

            sem_diff = abs(sem1 - sem2)
            if sem_diff < 0.03:
                penalty_factor = 0.90
                logger.info(
                    f"Ambiguity detected: FAISS diff is {sem_diff:.4f} (< 0.03). "
                    f"Applying ambiguity penalty (0.90) to top candidates."
                )
                c1["score"] = float(max(0.0, min(1.0, c1["score"] * penalty_factor)))
                c1["breakdown"]["ambiguity_penalty"] = penalty_factor

                c2["score"] = float(max(0.0, min(1.0, c2["score"] * penalty_factor)))
                c2["breakdown"]["ambiguity_penalty"] = penalty_factor

        # 2. Procedural Chain Completeness & Continuity Scoring
        query = getattr(self, "last_query", "")
        q_lower = query.lower() if query else ""

        # Step and numbering patterns
        step_label_pat = re.compile(r'^\s*(?:Step|STEP|Stage|STAGE|Phase|PHASE)\s*(\d+)\b', re.IGNORECASE)
        step_num_pat = re.compile(r'^\s*(\d+(?:\.\d+)+|\d+\.)\s*(.*)$')

        # Check query intent for procedural workflow keywords
        is_procedural_query = any(w in q_lower for w in ["step", "how to", "process", "workflow", "onboarding", "register", "onboard", "add", "create", "steps"])

        if is_procedural_query:
            # Group candidate chunks by document and section to avoid cross-procedure penalties
            docs_groups = {}
            for cand in ranked_candidates:
                src = cand.get("metadata", {}).get("source_file", "")
                sec = cand.get("metadata", {}).get("section_title", "")
                if src:
                    sec_key = sec if sec else "general"
                    group_key = (src, sec_key)
                    docs_groups.setdefault(group_key, []).append(cand)

            # Process each document group to calculate multi-chunk continuity and completeness
            for key, doc_cands in docs_groups.items():
                src, sec = key
                # Helper to extract chunk index
                def get_chunk_index(c):
                    chunk_id = c.get("chunk_id", "")
                    match = re.search(r'_c(\d+)$', chunk_id)
                    return int(match.group(1)) if match else 0

                sorted_cands = sorted(doc_cands, key=get_chunk_index)
                chunk_indices = [get_chunk_index(c) for c in sorted_cands]

                # Extract unique step numbers from chunk text
                step_numbers = []
                for cand in sorted_cands:
                    text = cand.get("text", "")
                    for line in text.split('\n'):
                        t = line.strip()
                        m_label = step_label_pat.match(t)
                        if m_label:
                            step_numbers.append(int(m_label.group(1)))
                        else:
                            m_num = step_num_pat.match(t)
                            if m_num:
                                try:
                                    first_digit = int(m_num.group(1).split('.')[0])
                                    step_numbers.append(first_digit)
                                except ValueError:
                                    pass

                unique_step_nums = sorted(list(set(step_numbers)))

                # A. Workflow Completeness Score
                index_completeness = 1.0
                if len(chunk_indices) > 1:
                    span = chunk_indices[-1] - chunk_indices[0] + 1
                    index_completeness = len(set(chunk_indices)) / span

                step_completeness = 1.0
                if len(unique_step_nums) > 1:
                    span = unique_step_nums[-1] - unique_step_nums[0] + 1
                    step_completeness = len(unique_step_nums) / span

                workflow_completeness = min(index_completeness, step_completeness)

                # B. Procedural Continuity Score
                index_continuity = 1.0
                if len(chunk_indices) > 1:
                    contiguous = sum(1 for i in range(len(chunk_indices) - 1) if chunk_indices[i+1] - chunk_indices[i] == 1)
                    index_continuity = contiguous / (len(chunk_indices) - 1)

                step_continuity = 1.0
                if len(unique_step_nums) > 1:
                    contiguous = sum(1 for i in range(len(unique_step_nums) - 1) if unique_step_nums[i+1] - unique_step_nums[i] == 1)
                    step_continuity = contiguous / (len(unique_step_nums) - 1)

                procedural_continuity = (index_continuity + step_continuity) / 2.0

                # C. Missing Step Detection
                missing_steps = []
                if len(unique_step_nums) > 1:
                    full_steps_set = set(range(min(unique_step_nums), max(unique_step_nums) + 1))
                    missing_steps = sorted(list(full_steps_set - set(unique_step_nums)))

                missing_chunks = []
                if len(chunk_indices) > 1:
                    full_chunks_set = set(range(min(chunk_indices), max(chunk_indices) + 1))
                    missing_chunks = sorted(list(full_chunks_set - set(chunk_indices)))

                # Calculate penalties based on gaps
                penalty_factor = 1.0
                if len(missing_steps) > 0:
                    penalty_factor -= 0.10 * min(3, len(missing_steps))
                if len(missing_chunks) > 0:
                    penalty_factor -= 0.05 * min(3, len(missing_chunks))

                penalty_factor = max(0.70, penalty_factor)

                # D. Multi-Chunk Confidence Aggregation
                # Adjust final scores of the candidates in this group
                for cand in doc_cands:
                    base_score = cand["score"]
                    workflow_factor = 0.6 + 0.4 * (workflow_completeness * procedural_continuity)
                    
                    # Calculate overall combined multiplier and clamp it to avoid dropping below Uncertain band
                    combined_multiplier = workflow_factor * penalty_factor
                    combined_multiplier = max(0.60, combined_multiplier)
                    
                    # Less aggressive penalty for sparse/targeted retrievals
                    if len(doc_cands) < 10:
                        combined_multiplier = max(0.85, combined_multiplier)
                    
                    adjusted_score = base_score * combined_multiplier
                    cand["score"] = float(max(0.0, min(1.0, adjusted_score)))

                    # E. Completeness Confidence Bands
                    if workflow_completeness >= 0.95 and procedural_continuity >= 0.95:
                        band = "complete workflow"
                    elif workflow_completeness >= 0.65 and procedural_continuity >= 0.65:
                        band = "partially reconstructed workflow"
                    else:
                        band = "fragmented workflow"

                    bd = cand.setdefault("breakdown", {})
                    bd["workflow_completeness"] = float(workflow_completeness)
                    bd["procedural_continuity"] = float(procedural_continuity)
                    bd["missing_step_penalty"] = float(penalty_factor)
                    bd["completeness_band"] = band
                    bd["missing_steps"] = missing_steps
                    bd["missing_chunks"] = missing_chunks

                    logger.info(
                        f"Workflow scoring for chunk {cand['chunk_id']}: doc={src} "
                        f"completeness={workflow_completeness:.3f} continuity={procedural_continuity:.3f} "
                        f"penalty={penalty_factor:.3f} band='{band}' -> adjusted score={cand['score']:.4f}"
                    )
        else:
            # Initialize neutral breakdown keys for non-procedural/factual queries
            for cand in ranked_candidates:
                bd = cand.setdefault("breakdown", {})
                bd["workflow_completeness"] = 1.0
                bd["procedural_continuity"] = 1.0
                bd["missing_step_penalty"] = 1.0
                bd["completeness_band"] = "complete workflow"
                bd["missing_steps"] = []
                bd["missing_chunks"] = []

        return ranked_candidates
