"""
entity_detectors.py
-------------------
Reusable, pattern-based entity type detectors for the retrieval scoring layer.

Design rules:
- Each detector returns True / False only.
- No special-casing of domain terms (GSTIN, portal names, etc.).
- Regex patterns are compiled once at import time for efficiency.
- Functions are pure (no side-effects, no logging).
- New detector types can be added without touching any other module.
"""

import re
from typing import Any, Callable, Dict, List

# ---------------------------------------------------------------------------
# Compiled Pattern Definitions
# ---------------------------------------------------------------------------

_URL_PATTERN = re.compile(
    r"https?://[^\s\]\)\"\'>]+",
    re.IGNORECASE
)

_PORTAL_URL_PATTERN = re.compile(
    # Matches bare domain references like www.example.com or portal.example.co.in
    r"\b(?:www\.|portal\.|app\.)[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(?:/[^\s]*)?\b",
    re.IGNORECASE
)

_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE
)

_PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,5}[\s\-]?\d{4,6}"
)

_GSTIN_PATTERN = re.compile(
    r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b"
)

_PAN_PATTERN = re.compile(
    r"\b[A-Z]{5}\d{4}[A-Z]{1}\b"
)

_DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE
)

_CURRENCY_PATTERN = re.compile(
    r"(?:₹|Rs\.?|INR|USD|\$|EUR|€)\s*[\d,]+(?:\.\d{1,2})?|\b[\d,]+(?:\.\d{1,2})?\s*(?:lakhs?|crores?|millions?)\b",
    re.IGNORECASE
)

_STEP_LIST_PATTERN = re.compile(
    r"(?:step\s*\d+|^\s*\d+[\.\)]\s+\w|\b(?:first|second|third|fourth|fifth|then|next|finally)\b)",
    re.IGNORECASE | re.MULTILINE
)

_DEFINITION_PATTERN = re.compile(
    r"\b(?:is defined as|refers? to|means?|i\.e\.|that is|in other words)\b",
    re.IGNORECASE
)

_REQUIREMENT_PATTERN = re.compile(
    r"\b(?:must|shall|should|required|mandatory|compulsory|obligatory|necessary)\b",
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Public Detector Functions
# ---------------------------------------------------------------------------

def contains_url(text: str) -> bool:
    """Returns True if the text contains an http/https URL."""
    return bool(_URL_PATTERN.search(text))


def contains_portal_link(text: str) -> bool:
    """Returns True if the text contains an http URL or a bare www./portal./app. domain."""
    return bool(_URL_PATTERN.search(text) or _PORTAL_URL_PATTERN.search(text))


def contains_email(text: str) -> bool:
    """Returns True if the text contains an email address."""
    return bool(_EMAIL_PATTERN.search(text))


def contains_phone(text: str) -> bool:
    """Returns True if the text contains a phone number."""
    return bool(_PHONE_PATTERN.search(text))


def contains_gstin(text: str) -> bool:
    """Returns True if the text contains a GSTIN (15-char alphanumeric tax ID) or mentions GST/GSTIN."""
    return bool(_GSTIN_PATTERN.search(text) or "gst" in text.lower())


def contains_pan(text: str) -> bool:
    """Returns True if the text contains an Indian PAN number or mentions PAN."""
    return bool(_PAN_PATTERN.search(text) or "pan" in text.lower())



def contains_date(text: str) -> bool:
    """Returns True if the text contains a formatted date."""
    return bool(_DATE_PATTERN.search(text))


def contains_currency(text: str) -> bool:
    """Returns True if the text contains a currency amount."""
    return bool(_CURRENCY_PATTERN.search(text))


def contains_step_list(text: str) -> bool:
    """Returns True if the text describes a numbered/ordered sequence of steps."""
    return bool(_STEP_LIST_PATTERN.search(text))


def contains_definition(text: str) -> bool:
    """Returns True if the text defines or explains a concept."""
    return bool(_DEFINITION_PATTERN.search(text))


def contains_requirement(text: str) -> bool:
    """Returns True if the text states a requirement or obligation."""
    return bool(_REQUIREMENT_PATTERN.search(text))


# ---------------------------------------------------------------------------
# Answer-Type Registry
# ---------------------------------------------------------------------------
# Maps a canonical answer-type label to:
#   - "query_signals"  : keywords that indicate the query seeks this type
#   - "detector"       : function that checks if a chunk supplies this type
#
# This registry drives answer-type-aware scoring. To add a new type, just
# append one entry here — no other code needs to change.

ANSWER_TYPE_REGISTRY: List[Dict] = [
    {
        "type": "url_link",
        "query_signals": ["link", "url", "website", "portal", "site", "web address", "portal address", "navigate to", "go to", "access", "open"],
        "detector": contains_portal_link,
    },
    {
        "type": "email",
        "query_signals": ["email", "mail", "contact", "write to", "send to"],
        "detector": contains_email,
    },
    {
        "type": "phone",
        "query_signals": ["phone", "call", "contact number", "helpline", "toll free", "hotline"],
        "detector": contains_phone,
    },
    {
        "type": "gstin",
        "query_signals": ["gstin", "gst number", "gst id", "tax number"],
        "detector": contains_gstin,
    },
    {
        "type": "pan",
        "query_signals": ["pan", "pan number", "pan card"],
        "detector": contains_pan,
    },
    {
        "type": "date",
        "query_signals": ["date", "when", "deadline", "timeline", "schedule", "by when"],
        "detector": contains_date,
    },
    {
        "type": "currency",
        "query_signals": ["cost", "price", "fee", "charges", "amount", "payment", "invoice", "rate"],
        "detector": contains_currency,
    },
    {
        "type": "step_procedure",
        "query_signals": ["how to", "steps", "procedure", "process", "instructions", "guide", "how do i", "how can i", "method"],
        "detector": contains_step_list,
    },
    {
        "type": "definition",
        "query_signals": ["what is", "define", "meaning of", "explain", "definition"],
        "detector": contains_definition,
    },
    {
        "type": "requirement",
        "query_signals": ["required", "mandatory", "must", "need to", "should", "what documents", "what are the requirements"],
        "detector": contains_requirement,
    },
]


def detect_query_answer_type(query: str) -> str:
    """
    Identifies the most likely answer type the query is seeking.

    Scans query tokens against each registry entry's signal keywords.
    Returns the canonical type label of the first match, or 'generic' if none match.

    Args:
        query (str): The preprocessed query string.

    Returns:
        str: Answer type label e.g. 'url_link', 'step_procedure', 'generic'.
    """
    query_lower = query.lower()
    for entry in ANSWER_TYPE_REGISTRY:
        if any(signal in query_lower for signal in entry["query_signals"]):
            return entry["type"]
    return "generic"


def chunk_satisfies_answer_type(chunk_text: str, answer_type: str) -> bool:
    """
    Checks whether the chunk text contains the expected answer entity type.

    Args:
        chunk_text (str): The verbatim chunk text.
        answer_type (str): The canonical answer type label from detect_query_answer_type().

    Returns:
        bool: True if the chunk contains the required answer entity type.
    """
    for entry in ANSWER_TYPE_REGISTRY:
        if entry["type"] == answer_type:
            return entry["detector"](chunk_text)
    return True  # 'generic' type — no entity constraint


# ---------------------------------------------------------------------------
# Procedural Intelligence Extensions
# ---------------------------------------------------------------------------

_STEP_NUM_CAPTURE = re.compile(
    r'(?:^\s*(?:Step|STEP|Stage|STAGE|Phase|PHASE)\s*(\d+(?:\.\d+)*)\b|^\s*(\d+(?:\.\d+)+|\d+)[\.\)]\s+)',
    re.MULTILINE
)

_SPECIFIC_PROCEDURAL_PATTERN = re.compile(
    r'\b(next|then|after\s+that|proceed\s+to|finally|submit)\b',
    re.IGNORECASE
)

_WORKFLOW_START_PATTERN = re.compile(
    r'\b(?:step\s*1\b|1\.1\b|1\.\s+|first(?:ly)?\b|login\s+to\b|to\s+begin\b|start\b|onboard\b|register\b)',
    re.IGNORECASE
)

_WORKFLOW_CONTINUATION_PATTERN = re.compile(
    r'\b(?:step\s*[2-9]\b|step\s*\d{2,}\b|\d+\.\d+\b|[2-9]\.\s+|\d{2,}\.\s+|next\b|then\b|after\s+that\b|subsequently\b|proceed\b)',
    re.IGNORECASE
)

_WORKFLOW_ENDING_PATTERN = re.compile(
    r'\b(?:finally\b|lastly\b|end\b|submit\b|save\b|complete\b|success\b|request\s*id\b|notification\s*email\b)',
    re.IGNORECASE
)


def extract_step_numbers(text: str) -> List[str]:
    """
    Extracts step numbers from the text (e.g. '1', '1.1', '2').
    Returns a sorted list of unique step strings found.
    """
    if not text:
        return []
    
    matches = _STEP_NUM_CAPTURE.findall(text)
    step_nums = []
    for m in matches:
        val = m[0] or m[1]
        if val:
            cleaned = val.strip('.')
            if cleaned not in step_nums:
                step_nums.append(cleaned)
                
    return step_nums


def has_procedural_keywords(text: str) -> bool:
    """Returns True if specific workflow progression keywords are present."""
    return bool(_SPECIFIC_PROCEDURAL_PATTERN.search(text))


def detect_workflow_boundary(text: str) -> Dict[str, bool]:
    """
    Identifies the presence of workflow boundaries (start, continuation, ending) in the text.
    """
    return {
        "start": bool(_WORKFLOW_START_PATTERN.search(text)),
        "continuation": bool(_WORKFLOW_CONTINUATION_PATTERN.search(text)),
        "ending": bool(_WORKFLOW_ENDING_PATTERN.search(text))
    }


def compute_procedural_density(text: str) -> float:
    """
    Measures how strongly a chunk represents procedural instructions or ordered workflows.
    Returns a score between 0.0 and 1.0.
    """
    if not text:
        return 0.0
        
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return 0.0
        
    procedural_lines = 0
    step_num_count = 0
    
    progression_matches = len(_SPECIFIC_PROCEDURAL_PATTERN.findall(text))
    action_verbs = len(re.findall(r'\b(?:click|select|choose|enter|fill|upload|verify|log|navigate|check|submit|save|add|update)\b', text, re.IGNORECASE))
    
    for line in lines:
        is_step = bool(_STEP_NUM_CAPTURE.search(line))
        is_action = any(verb in line.lower() for verb in ["click", "select", "choose", "enter", "fill", "upload", "verify", "log", "navigate", "submit"])
        if is_step:
            step_num_count += 1
        if is_step or is_action:
            procedural_lines += 1
            
    line_ratio = procedural_lines / len(lines)
    step_ratio = min(1.0, step_num_count / 3.0)
    verb_ratio = min(1.0, action_verbs / 5.0)
    keyword_ratio = min(1.0, progression_matches / 2.0)
    
    density = (0.4 * line_ratio) + (0.3 * step_ratio) + (0.2 * verb_ratio) + (0.1 * keyword_ratio)
    
    return float(max(0.0, min(1.0, density)))


def extract_step_continuity(text: str) -> Dict[str, Any]:
    """
    Extracts step numbers, sequences, and workflow progression markers from the text.
    """
    step_numbers = extract_step_numbers(text)
    
    markers = []
    for marker in ["first", "second", "third", "fourth", "fifth", "then", "next", "finally", "after that", "proceed to", "submit"]:
        if re.search(r'\b' + re.escape(marker) + r'\b', text, re.IGNORECASE):
            markers.append(marker)
            
    numeric_steps = []
    for sn in step_numbers:
        parts = sn.split('.')
        try:
            val = float(parts[0]) if len(parts) == 1 else float(f"{parts[0]}.{parts[1]}")
            numeric_steps.append(val)
        except ValueError:
            pass
            
    is_ordered = True
    if len(numeric_steps) > 1:
        for i in range(len(numeric_steps) - 1):
            if numeric_steps[i+1] < numeric_steps[i]:
                is_ordered = False
                break
                
    return {
        "step_numbers": step_numbers,
        "numeric_sequence": numeric_steps,
        "is_ordered_sequence": is_ordered,
        "progression_markers": markers
    }
