import logging
import re
from typing import Any, Dict, List, Union, Optional, Tuple

logger = logging.getLogger(__name__)

# Compile regex patterns once at import time
SECTION_RE = re.compile(
    r'^\s*(?:[A-Z]\.\s+([A-Z0-9][A-Za-z0-9\s:,\-\(\)/&]{2,100}\.?)|[Tt]able\s+of\s+[Cc]ontents|[Aa]dditional\s+[Ii]nformation)\s*$'
)

ENTERPRISE_SECTION_RE = re.compile(
    r'^\s*(?:(?:[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)\s*[-.:]?\s+)?(Purpose|Scope|Eligibility|Applicability|Prerequisites|Overview|Introduction|Description|Notes|Definitions|Responsibilities|Process|Procedure|Steps|Approval\s+Matrix|Business\s+Rules|Inputs|Outputs)\s*[:.]?\s*$',
    re.IGNORECASE
)

SUBSECTION_RE = re.compile(
    r'^\s*(Step|Stage|Phase)\s+(\d+)\s*(?::|\.|\s-)\s*(.+)$',
    re.IGNORECASE
)

STEP_BOUNDARY_RE = re.compile(
    r'^\s*(?:(?:Step|Stage|Phase)\s*\d+|(?:\d+(?:\.\d+)*)[\.\)]?\s+\w|[\-\*\u2022]\s+\w)',
    re.IGNORECASE
)


def parse_heading(line: str, current_section: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Parse a line to detect section or subsection headings.

    Returns a tuple (heading_type, heading_text) where heading_type is "section",
    "subsection", or None. Promotes a subsection to a section when there is no
    current_section context or it is "Table of Contents".
    """
    stripped = line.strip()
    if not stripped:
        return (None, None)

    # Detect top-level sections
    match = SECTION_RE.match(stripped) or ENTERPRISE_SECTION_RE.match(stripped)
    if match:
        # SECTION_RE may capture group 1 as title; fallback to whole line
        title = match.group(1) if match.lastindex and match.lastindex >= 1 else stripped
        return ("section", title.strip())

    # Detect subsections like "Step 1: Title"
    sub_match = SUBSECTION_RE.match(stripped)
    if sub_match:
        title = sub_match.group(3).strip()
        if not current_section or current_section.lower() == "table of contents":
            return ("section", title)
        return ("subsection", title)

    return (None, None)


def slugify(text: str) -> str:
    """Creates a basic alphanumeric slug for IDs."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


def slugify_filename(filename: str) -> str:
    """Slugs a file name, ignoring the PDF extension."""
    if filename.lower().endswith(".pdf"):
        filename = filename[:-4]
    return slugify(filename)


def generate_procedure_id(source_file: str, section_title: str, subsection_title: str) -> str:
    """Generates a deterministic procedure ID slug."""
    parts = [slugify_filename(source_file)]
    if section_title:
        parts.append(slugify(section_title))
    if subsection_title:
        parts.append(slugify(subsection_title))
    if len(parts) == 1:
        parts.append("proc")
    return "_".join(parts)


def extract_step_numbers(text: str) -> List[str]:
    """Extracts step numbers sequentially as they appear in the text."""
    if not text:
        return []
    pattern = re.compile(
        r'(?:^\s*(?:Step|STEP|Stage|STAGE|Phase|PHASE)\s*(\d+(?:\.\d+)*)\b|^\s*(\d+(?:\.\d+)+|\d+)[\.\)]\s+)',
        re.MULTILINE | re.IGNORECASE
    )
    matches = pattern.findall(text)
    step_nums = []
    for m in matches:
        val = m[0] or m[1]
        if val:
            cleaned = val.strip('.')
            if cleaned not in step_nums:
                step_nums.append(cleaned)
    return step_nums





BOILERPLATE_PATTERNS = [
    re.compile(r'^\s*Add\s+Delivery\s+Location\s*$', re.IGNORECASE),
    re.compile(r'^\s*\d+\s*\|\s*P\s*a\s*g\s*e\s*$', re.IGNORECASE),
    re.compile(r'^\s*STRICTLY\s+FOR\s+INTERNAL\s+CIRCULATION\s+ONLY\s*$', re.IGNORECASE),
    re.compile(r'^\s*New\s+Merchandise\s+Vendor\s+Registration.*$', re.IGNORECASE),
    re.compile(r'^\s*Page\s+\d+\s+of\s+\d+\s*$', re.IGNORECASE),
    re.compile(r'^_+$')
]


def is_boilerplate_line(line: str) -> bool:
    """Checks if a line contains only standard manual headers, footers, or page numbers."""
    line_stripped = line.strip()
    if not line_stripped:
        return True
    for pat in BOILERPLATE_PATTERNS:
        if pat.match(line_stripped):
            return True
    return False


def has_block_content(block_lines: List[str]) -> bool:
    """Returns True if the block contains at least one line of genuine instructional content."""
    for line in block_lines:
        if is_boilerplate_line(line):
            continue
        heading_type, _ = parse_heading(line)
        if heading_type:
            continue
        return True
    return False


def group_lines_into_steps(lines: List[str]) -> List[List[str]]:
    """Groups consecutive lines of a block into logical instruction steps."""
    step_units = []
    current_unit = []
    
    for line in lines:
        line_stripped = line.strip()
        is_boundary = bool(STEP_BOUNDARY_RE.match(line_stripped))
        is_heading = bool(
            SECTION_RE.match(line_stripped) or
            ENTERPRISE_SECTION_RE.match(line_stripped) or
            SUBSECTION_RE.match(line_stripped)
        )
        
        if (is_boundary or is_heading) and current_unit:
            step_units.append(current_unit)
            current_unit = []
            
        current_unit.append(line)
        
    if current_unit:
        step_units.append(current_unit)
        
    return step_units


class RecursiveCharacterTextSplitter:
    """
    A standalone, production-grade recursive character text splitter.
    Splits text by trying a sequence of separators in order to keep paragraphs,
    sentences, and words together as much as possible, while enforcing a maximum chunk size
    and including a sliding window overlap.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: List[str] = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        separator = separators[0]
        next_separators = separators[1:]

        if separator == "":
            splits = list(text)
        else:
            splits = text.split(separator)

        final_splits = []
        for s in splits:
            if len(s) <= self.chunk_size:
                final_splits.append(s)
            else:
                final_splits.extend(self._split_text(s, next_separators))

        return final_splits

    def split(self, text: str) -> List[str]:
        if not text:
            return []

        raw_splits = self._split_text(text, self.separators)

        chunks = []
        current_chunk_tokens = []
        current_length = 0

        for split in raw_splits:
            split_len = len(split)
            join_len = 1 if current_chunk_tokens else 0
            
            if current_length + split_len + join_len <= self.chunk_size:
                current_chunk_tokens.append(split)
                current_length += split_len + join_len
            else:
                if current_chunk_tokens:
                    chunks.append(" ".join(current_chunk_tokens).strip())
                
                new_tokens = [split]
                new_len = split_len
                
                for prev_token in reversed(current_chunk_tokens):
                    prev_len = len(prev_token)
                    prev_join_len = 1 if new_tokens else 0
                    if new_len + prev_len + prev_join_len <= self.chunk_overlap:
                        new_tokens.insert(0, prev_token)
                        new_len += prev_len + prev_join_len
                    else:
                        break
                
                current_chunk_tokens = new_tokens
                current_length = new_len

        if current_chunk_tokens:
            chunks.append(" ".join(current_chunk_tokens).strip())

        return [c for c in chunks if c]


class DocumentChunker:
    """
    A production-grade Document Chunker managing multiple segmenting strategies.
    Attributes chunks directly to individual pages to keep metadata and page citations accurate.
    Evolved to support structure-aware, heading-aware, and procedure-aware chunking.
    """

    def __init__(
        self,
        strategy: str = "recursive",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        self.strategy = strategy.lower()
        if self.strategy not in ["recursive", "page"]:
            raise ValueError(f"Unsupported strategy: {strategy}. Use 'recursive' or 'page'.")
            
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Keep a default splitter for character-level fallbacks
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        
        # Persistent state across pages
        self.current_section_title = None
        self.current_subsection_title = None

    def _parse_page_blocks(self, clean_text: str) -> List[Dict[str, Any]]:
        lines = clean_text.split('\n')
        blocks = []
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                if blocks:
                    blocks[-1]["lines"].append(line)
                continue
                
            heading_type, heading_text = parse_heading(line, self.current_section_title)
            if heading_type == "section":
                self.current_section_title = heading_text
                self.current_subsection_title = None
                blocks.append({
                    "section_title": self.current_section_title,
                    "subsection_title": self.current_subsection_title,
                    "lines": [line]
                })
                continue
                
            if heading_type == "subsection":
                self.current_subsection_title = heading_text
                blocks.append({
                    "section_title": self.current_section_title,
                    "subsection_title": self.current_subsection_title,
                    "lines": [line]
                })
                continue
                
            if not blocks:
                blocks.append({
                    "section_title": self.current_section_title,
                    "subsection_title": self.current_subsection_title,
                    "lines": []
                })
            
            blocks[-1]["lines"].append(line)
            
        return blocks

    def _assemble_chunks_from_steps(
        self,
        step_units: List[List[str]],
        section_title: str,
        subsection_title: str
    ) -> List[str]:
        if not step_units:
            return []
            
        chunks = []
        i = 0
        num_units = len(step_units)
        
        while i < num_units:
            prefix_lines = []
            if section_title:
                prefix_lines.append(section_title)
            if subsection_title:
                prefix_lines.append(subsection_title)
            
            def get_formatted_length(units):
                body_text = "\n".join("\n".join(u) for u in units).strip()
                actual_prefix = ""
                if section_title and not body_text.startswith(section_title):
                    actual_prefix += f"{section_title}\n"
                if subsection_title and not body_text.startswith(subsection_title):
                    actual_prefix += f"{subsection_title}\n"
                return len(actual_prefix) + len(body_text)
                
            current_units = [step_units[i]]
            last_added_idx = i
            i += 1
            
            while i < num_units:
                potential_units = current_units + [step_units[i]]
                if get_formatted_length(potential_units) <= self.chunk_size:
                    current_units.append(step_units[i])
                    last_added_idx = i
                    i += 1
                else:
                    break
            
            # Check if single unit exceeds limit, trigger character fallback
            if get_formatted_length(current_units) > self.chunk_size:
                unit_text = "\n".join(step_units[last_added_idx]).strip()
                actual_prefix = ""
                if section_title and not unit_text.startswith(section_title):
                    actual_prefix += f"{section_title}\n"
                if subsection_title and not unit_text.startswith(subsection_title):
                    actual_prefix += f"{subsection_title}\n"
                
                rem_size = max(1, self.chunk_size - len(actual_prefix))
                fallback_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=rem_size,
                    chunk_overlap=self.chunk_overlap
                )
                sub_splits = fallback_splitter.split(unit_text)
                for sub_text in sub_splits:
                    chunks.append((actual_prefix + sub_text).strip())
            else:
                body_text = "\n".join("\n".join(u) for u in current_units).strip()
                actual_prefix = ""
                if section_title and not body_text.startswith(section_title):
                    actual_prefix += f"{section_title}\n"
                if subsection_title and not body_text.startswith(subsection_title):
                    actual_prefix += f"{subsection_title}\n"
                
                chunk_text = (actual_prefix + body_text).strip()
                chunks.append(chunk_text)
                
            if i >= num_units:
                break
                
            if len(current_units) > 1:
                i = last_added_idx
                
        # Merge tiny chunks with previous chunk if safe to avoid low-information fragments
        merged_chunks = []
        tiny_threshold = min(150, self.chunk_size // 3)
        for chunk_text in chunks:
            if not chunk_text.strip():
                continue
            if not merged_chunks:
                merged_chunks.append(chunk_text)
                continue
            
            prev_chunk = merged_chunks[-1]
            # Check if either chunk is tiny (e.g. < tiny_threshold characters)
            # and combined length fits in chunk_size + tiny_threshold
            if (len(chunk_text) < tiny_threshold or len(prev_chunk) < tiny_threshold) and (len(prev_chunk) + len(chunk_text) + 1 <= self.chunk_size + tiny_threshold):
                prev_lines = prev_chunk.split('\n')
                curr_lines = chunk_text.split('\n')
                
                common_count = 0
                for pl, cl in zip(prev_lines, curr_lines):
                    if pl.strip() == cl.strip():
                        common_count += 1
                    else:
                        break
                
                suffix = "\n".join(curr_lines[common_count:])
                if suffix.strip():
                    if suffix.strip() not in prev_chunk:
                        merged_chunks[-1] = prev_chunk + "\n" + suffix
            else:
                merged_chunks.append(chunk_text)
                
        return merged_chunks

    def chunk_document(self, preprocessed_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        doc_id = preprocessed_doc["doc_id"]
        source_file = preprocessed_doc["source_file"]
        pages = preprocessed_doc["pages"]
        
        chunks_output: List[Dict[str, Any]] = []
        
        self.current_section_title = None
        self.current_subsection_title = None
        
        for page_index, page_data in enumerate(pages):
            page_num = page_data["page_number"]
            clean_text = page_data["clean_text"]

            if not clean_text:
                continue

            if self.strategy == "page":
                for line in clean_text.split('\n'):
                    heading_type, heading_text = parse_heading(line, self.current_section_title)
                    if heading_type == "section":
                        self.current_section_title = heading_text
                        self.current_subsection_title = None
                    elif heading_type == "subsection":
                        self.current_subsection_title = heading_text
                        
                chunks_output.append({
                    "chunk_id": "",
                    "doc_id": doc_id,
                    "source_file": source_file,
                    "page_number": page_num,
                    "chunk_index": 0,
                    "text": clean_text,
                    "metadata": {
                        "source_file": source_file,
                        "page_number": page_num,
                        "char_count": len(clean_text),
                        "section_title": self.current_section_title,
                        "subsection_title": self.current_subsection_title,
                        "procedure_id": generate_procedure_id(source_file, self.current_section_title, self.current_subsection_title),
                        "chunk_position": "",
                        "page_order": page_index,
                        "detected_step_numbers": extract_step_numbers(clean_text)
                    }
                })
            else:
                blocks = self._parse_page_blocks(clean_text)
                
                for block in blocks:
                    block_lines = block["lines"]
                    if not has_block_content(block_lines):
                        continue
                        
                    sec_title = block["section_title"]
                    subsec_title = block["subsection_title"]
                    
                    step_units = group_lines_into_steps(block_lines)
                    block_chunks = self._assemble_chunks_from_steps(step_units, sec_title, subsec_title)
                    
                    for split_text in block_chunks:
                        if not split_text.strip():
                            continue
                            
                        chunks_output.append({
                            "chunk_id": "",
                            "doc_id": doc_id,
                            "source_file": source_file,
                            "page_number": page_num,
                            "chunk_index": 0,
                            "text": split_text,
                            "metadata": {
                                "source_file": source_file,
                                "page_number": page_num,
                                "char_count": len(split_text),
                                "section_title": sec_title,
                                "subsection_title": subsec_title,
                                "procedure_id": generate_procedure_id(source_file, sec_title, subsec_title),
                                "chunk_position": "",
                                "page_order": page_index,
                                "detected_step_numbers": extract_step_numbers(split_text)
                            }
                        })

        # Deduplicate exact duplicate chunks (same page number and same text content)
        deduplicated_chunks = []
        seen_chunks = set()
        for chunk in chunks_output:
            key = (chunk["page_number"], chunk["text"])
            if key not in seen_chunks:
                seen_chunks.add(key)
                deduplicated_chunks.append(chunk)
        chunks_output = deduplicated_chunks

        total_chunks = len(chunks_output)
        for idx, chunk in enumerate(chunks_output):
            chunk["chunk_index"] = idx
            chunk["chunk_id"] = f"{doc_id}_c{idx}"
            
            if total_chunks == 1:
                pos = "start"
            elif idx == 0:
                pos = "start"
            elif idx == total_chunks - 1:
                pos = "end"
            else:
                pos = "middle"
                
            chunk["metadata"]["chunk_position"] = pos

        logger.info(
            f"Segmented {source_file} into {total_chunks} chunk(s) using '{self.strategy}' strategy."
        )
        return chunks_output


# Example usage block
if __name__ == "__main__":
    test_doc = {
        "doc_id": "mock_doc_123",
        "source_file": "user_guide.pdf",
        "pages": [
            {
                "page_number": 1,
                "clean_text": "This is page 1.\nIt describes the basic setup of the vendor location system.\nFirst, open the application. Next, insert your credentials.\n"
            },
            {
                "page_number": 2,
                "clean_text": "This is page 2.\nIt details how to configure delivery coordinates.\nSelect coordinates on the map. Save your delivery configuration details."
            }
        ]
    }
    
    chunker = DocumentChunker(strategy="recursive", chunk_size=80, chunk_overlap=15)
    result = chunker.chunk_document(test_doc)
    import json
    print("Recursive splits:")
    print(json.dumps(result, indent=2))
