"""Validation and parsing utilities for prose-editor skill."""

import re
from pathlib import Path
from typing import Any, Dict, List

ALLOWED_CATEGORIES = {"Clarity", "Brevity", "Flow", "Tone", "Grammar", "Structure"}
ALLOWED_IMPACTS = {"Major", "Minor", "Nit"}
PROSE_EXTENSIONS = {".md", ".markdown", ".rst", ".txt", ".tex", ".adoc"}


def is_prose_file(file_path: str | Path) -> bool:
    """Return True if file path has a supported prose/markup extension."""
    suffix = Path(file_path).suffix.lower()
    return suffix in PROSE_EXTENSIONS


def extract_protected_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract syntax blocks that must be preserved verbatim in prose."""
    protected: List[Dict[str, Any]] = []

    # 1. Fenced code blocks (``` ... ```)
    for match in re.finditer(r"```[\s\S]*?```", text):
        protected.append({"type": "code_block", "content": match.group(0), "span": match.span()})

    # 2. LaTeX math blocks ($$ ... $$)
    for match in re.finditer(r"\$\$[\s\S]*?\$\$", text):
        protected.append({"type": "math_block", "content": match.group(0), "span": match.span()})

    # 3. Alert callouts (> [!NOTE], > [!WARNING], etc.)
    for match in re.finditer(r"^>[ \t]*\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][^\n]*", text, re.MULTILINE):
        protected.append({"type": "callout_alert", "content": match.group(0), "span": match.span()})

    # 4. Markdown tables (| header | ... |)
    for match in re.finditer(r"(?:^\|[^\n]+\|\r?\n){2,}", text, re.MULTILINE):
        protected.append({"type": "table", "content": match.group(0), "span": match.span()})

    # 5. Task list items (- [ ] / - [x])
    for match in re.finditer(r"^[ \t]*-[ \t]+\[[ xX]\][^\n]*", text, re.MULTILINE):
        protected.append({"type": "task_list_item", "content": match.group(0), "span": match.span()})

    # 6. Footnotes ([^1]: ...)
    for match in re.finditer(r"^\[\^[a-zA-Z0-9_-]+\]:[^\n]*", text, re.MULTILINE):
        protected.append({"type": "footnote", "content": match.group(0), "span": match.span()})

    return protected


def parse_suggestion_cards(text: str) -> List[Dict[str, Any]]:
    """Parse markdown suggestion cards into structured dicts with schema validation."""
    card_header_pattern = re.compile(
        r"^###\s+Suggestion\s+#(\d+)\s+`\[([a-zA-Z]+)\]`\s+`\[([a-zA-Z]+)\]`",
        re.MULTILINE,
    )

    matches = list(card_header_pattern.finditer(text))
    if not matches:
        return []

    cards: List[Dict[str, Any]] = []

    for i, match in enumerate(matches):
        card_id = int(match.group(1))
        category = match.group(2)
        impact = match.group(3)

        if category not in ALLOWED_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Allowed: {sorted(ALLOWED_CATEGORIES)}")
        if impact not in ALLOWED_IMPACTS:
            raise ValueError(f"Invalid impact '{impact}'. Allowed: {sorted(ALLOWED_IMPACTS)}")

        # Slice content until next card or EOF
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start_pos:end_pos]

        anchor_match = re.search(r"^-\s+\*\*Anchor:\*\*\s*(.+)$", body, re.MULTILINE)
        original_match = re.search(r"^-\s+\*\*Original:\*\*\s*\"([\s\S]*?)\"$", body, re.MULTILINE)
        proposed_match = re.search(r"^-\s+\*\*Proposed:\*\*\s*\"([\s\S]*?)\"$", body, re.MULTILINE)
        rationale_match = re.search(r"^-\s+\*\*Rationale:\*\*\s*(.+)$", body, re.MULTILINE)

        if not anchor_match:
            raise ValueError(f"Missing required field 'Anchor' in Suggestion #{card_id}")
        if not original_match:
            raise ValueError(f"Missing required field 'Original' in Suggestion #{card_id}")
        if not proposed_match:
            raise ValueError(f"Missing required field 'Proposed' in Suggestion #{card_id}")
        if not rationale_match:
            raise ValueError(f"Missing required field 'Rationale' in Suggestion #{card_id}")

        cards.append(
            {
                "id": card_id,
                "category": category,
                "impact": impact,
                "anchor": anchor_match.group(1).strip(),
                "original": original_match.group(1),
                "proposed": proposed_match.group(1),
                "rationale": rationale_match.group(1).strip(),
            }
        )

    return cards


def validate_verbatim_quotes(cards: List[Dict[str, Any]], source_text: str) -> bool:
    """Ensure every card's original snippet exists verbatim as a substring of source_text."""
    for card in cards:
        orig = card.get("original", "")
        card_id = card.get("id", "?")
        if orig not in source_text:
            raise ValueError(f"Verbatim quote mismatch for Suggestion #{card_id}: original text was not found in source")
    return True


def format_clean_summary(total_words: int, reading_time_min: int) -> str:
    """Format standard clean document summary when 0 suggestions are found."""
    return f"""### Prose Review Summary: Clean Document
- **Total Suggestions:** 0
- **Document Length:** {total_words:,} words (~{reading_time_min} min read)
- **Status:** Clean prose with consistent voice and strong structural flow; No edits recommended.
"""
