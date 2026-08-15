"""Validation and parsing utilities for prose-editor skill."""

import json
from pathlib import Path
import re
from typing import Any, Dict, List

SCHEMA_PATH = Path(__file__).parent / "suggestion_schema.json"

if SCHEMA_PATH.exists():
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            _schema = json.load(f)
            ALLOWED_CATEGORIES = set(_schema["properties"]["category"]["enum"])
            ALLOWED_IMPACTS = set(_schema["properties"]["impact"]["enum"])
    except Exception:
        ALLOWED_CATEGORIES = {"Clarity", "Brevity", "Flow", "Tone", "Grammar", "Structure"}
        ALLOWED_IMPACTS = {"Major", "Minor", "Nit"}
else:
    ALLOWED_CATEGORIES = {"Clarity", "Brevity", "Flow", "Tone", "Grammar", "Structure"}
    ALLOWED_IMPACTS = {"Major", "Minor", "Nit"}

PROSE_EXTENSIONS = {".md", ".markdown", ".rst", ".txt", ".tex", ".adoc"}


def is_prose_file(file_path: str | Path) -> bool:
    """Return True if file path has a supported prose/markup extension."""
    suffix = Path(file_path).suffix.lower()
    return suffix in PROSE_EXTENSIONS


def extract_protected_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract syntax and structural blocks that must be preserved verbatim in prose."""
    protected: List[Dict[str, Any]] = []

    # 1. YAML frontmatter (^---\n[\s\S]*?\n---)
    frontmatter_match = re.match(r"^---\r?\n[\s\S]*?\r?\n---", text)
    if frontmatter_match:
        protected.append({"type": "frontmatter", "content": frontmatter_match.group(0), "span": frontmatter_match.span()})

    # 2. Fenced code blocks (``` ... ``` or ~~~ ... ~~~, fail-closed for unclosed blocks to EOF)
    for match in re.finditer(r"(?:```[\s\S]*?(?:```|$)|~~~[\s\S]*?(?:~~~|$))", text):
        if match.group(0).strip():
            protected.append({"type": "code_block", "content": match.group(0), "span": match.span()})

    # 3. LaTeX math blocks ($$ ... $$, fail-closed to EOF)
    for match in re.finditer(r"\$\$[\s\S]*?(?:\$\$|$)", text):
        if match.group(0).strip():
            protected.append({"type": "math_block", "content": match.group(0), "span": match.span()})

    # 4. Alert callouts (> [!NOTE], > [!WARNING], etc.)
    for match in re.finditer(r"^>[ \t]*\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][^\n]*", text, re.MULTILINE):
        protected.append({"type": "callout_alert", "content": match.group(0), "span": match.span()})

    # 5. Markdown tables (| header | ... |, handles tables at EOF without trailing newline)
    for match in re.finditer(r"(?:^\|[^\n]+\|\r?\n?){2,}", text, re.MULTILINE):
        protected.append({"type": "table", "content": match.group(0), "span": match.span()})

    # 6. Task list items (- [ ] / - [x])
    for match in re.finditer(r"^[ \t]*-[ \t]+\[[ xX]\][^\n]*", text, re.MULTILINE):
        protected.append({"type": "task_list_item", "content": match.group(0), "span": match.span()})

    # 7. Footnote definitions ([^1]: ...) and references ([^1])
    for match in re.finditer(r"^\[\^[a-zA-Z0-9_-]+\]:[^\n]*", text, re.MULTILINE):
        protected.append({"type": "footnote_def", "content": match.group(0), "span": match.span()})
    for match in re.finditer(r"\[\^[a-zA-Z0-9_-]+\](?!:)", text):
        protected.append({"type": "footnote_ref", "content": match.group(0), "span": match.span()})

    # 8. Inline code (`...`)
    for match in re.finditer(r"`[^`\r\n]+`", text):
        protected.append({"type": "inline_code", "content": match.group(0), "span": match.span()})

    # 9. Inline math ($...$)
    for match in re.finditer(r"(?<!\$)\$(?!\$)[^\$\r\n]+(?<!\$)\$(?!\$)", text):
        protected.append({"type": "inline_math", "content": match.group(0), "span": match.span()})

    # 10. HTML tags (<tag> ... </tag> or <tag/>)
    for match in re.finditer(r"<[a-zA-Z/][^>\r\n]*>", text):
        protected.append({"type": "html_tag", "content": match.group(0), "span": match.span()})

    # 11. Markdown link targets / URLs ([text](url) or raw http://)
    for match in re.finditer(r"\[[^\]]+\]\([^)]+\)|https?://[^\s\)]+", text):
        protected.append({"type": "link_url", "content": match.group(0), "span": match.span()})

    return protected


def _extract_quoted_field(field_name: str, body: str, card_id: int) -> str:
    """Extract a quoted field value supporting multiline text, trailing whitespace, and curly quotes."""
    # Matches - **Field:** ["“]...["”][optional whitespace]$
    # Negative lookahead (?!\\n-\\s+\\*\\*) ensures quote does not bleed into subsequent field definitions
    pattern = re.compile(
        r"^-\s+\*\*" + re.escape(field_name) + r":\*\*\s*[\"“]((?:(?!\n-\s+\*\*)[\s\S])*?)[\"”]\s*$",
        re.MULTILINE,
    )
    match = pattern.search(body)
    if match:
        return match.group(1)

    # Check if field header was declared but quote was unterminated / malformed
    header_pattern = re.compile(r"^-\s+\*\*" + re.escape(field_name) + r":\*\*", re.MULTILINE)
    if header_pattern.search(body):
        raise ValueError(f"Unterminated or malformed quoted '{field_name}' in Suggestion #{card_id}")

    raise ValueError(f"Missing required field '{field_name}' in Suggestion #{card_id}")


def parse_suggestion_cards(text: str) -> List[Dict[str, Any]]:
    """Parse markdown suggestion cards into structured dicts with strict schema validation."""
    # 1. Detect any malformed suggestion headers before parsing
    for line in text.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("### Suggestion"):
            valid_header = re.match(
                r"^###\s+Suggestion\s+#(\d+)\s+`\[([a-zA-Z]+)\]`\s+`\[([a-zA-Z]+)\]`\s*$",
                trimmed,
            )
            if not valid_header:
                raise ValueError(f"Malformed suggestion header: '{trimmed}'")

    card_header_pattern = re.compile(
        r"^###\s+Suggestion\s+#(\d+)\s+`\[([a-zA-Z]+)\]`\s+`\[([a-zA-Z]+)\]`\s*$",
        re.MULTILINE,
    )

    matches = list(card_header_pattern.finditer(text))
    if not matches:
        return []

    cards: List[Dict[str, Any]] = []
    expected_id = 1
    seen_ids = set()

    for i, match in enumerate(matches):
        card_id = int(match.group(1))
        category = match.group(2)
        impact = match.group(3)

        if card_id <= 0:
            raise ValueError(f"Suggestion ID must be positive (>= 1), got #{card_id}")
        if card_id in seen_ids:
            raise ValueError(f"Duplicate suggestion ID #{card_id}")
        if card_id != expected_id:
            raise ValueError(f"Non-sequential suggestion ID: expected #{expected_id}, got #{card_id}")
        seen_ids.add(card_id)
        expected_id += 1

        if category not in ALLOWED_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Allowed: {sorted(ALLOWED_CATEGORIES)}")
        if impact not in ALLOWED_IMPACTS:
            raise ValueError(f"Invalid impact '{impact}'. Allowed: {sorted(ALLOWED_IMPACTS)}")

        # Slice body content until next card header or EOF
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start_pos:end_pos]

        anchor_match = re.search(r"^-\s+\*\*Anchor:\*\*\s*(.+)$", body, re.MULTILINE)
        if not anchor_match:
            raise ValueError(f"Missing required field 'Anchor' in Suggestion #{card_id}")

        original_val = _extract_quoted_field("Original", body, card_id)
        proposed_val = _extract_quoted_field("Proposed", body, card_id)

        rationale_match = re.search(r"^-\s+\*\*Rationale:\*\*\s*(.+)$", body, re.MULTILINE)
        if not rationale_match:
            raise ValueError(f"Missing required field 'Rationale' in Suggestion #{card_id}")

        if original_val == proposed_val:
            raise ValueError(f"No-op suggestion in Suggestion #{card_id}: Original and Proposed are identical")

        cards.append(
            {
                "id": card_id,
                "category": category,
                "impact": impact,
                "anchor": anchor_match.group(1).strip(),
                "original": original_val,
                "proposed": proposed_val,
                "rationale": rationale_match.group(1).strip(),
            }
        )

    return cards


def validate_verbatim_quotes(cards: List[Dict[str, Any]], source_text: str) -> bool:
    """Ensure every card's original snippet exists verbatim and unambiguously in source_text."""
    # Normalize CRLF in source and cards
    normalized_source = source_text.replace("\r\n", "\n")

    for card in cards:
        orig = card.get("original", "").replace("\r\n", "\n")
        card_id = card.get("id", "?")
        count = normalized_source.count(orig)
        if count == 0:
            raise ValueError(f"Verbatim quote mismatch for Suggestion #{card_id}: original text was not found in source")
        if count > 1:
            raise ValueError(
                f"Ambiguous verbatim quote for Suggestion #{card_id}: original text appears {count} times in source. "
                "Include surrounding anchor context."
            )
    return True


def format_clean_summary(total_words: int, reading_time_min: int) -> str:
    """Format standard clean document summary when 0 suggestions are found."""
    return f"""### Prose Review Summary: Clean Document
- **Total Suggestions:** 0
- **Document Length:** {total_words:,} words (~{reading_time_min} min read)
- **Status:** Clean prose with consistent voice and strong structural flow; No edits recommended.
"""
