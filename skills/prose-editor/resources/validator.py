"""Validation and parsing utilities for prose-editor skill."""

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List

SCHEMA_PATH = Path(__file__).parent / "suggestion_schema.json"

if SCHEMA_PATH.exists():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        try:
            _schema = json.load(f)
            ALLOWED_CATEGORIES = set(_schema["properties"]["category"]["enum"])
            ALLOWED_IMPACTS = set(_schema["properties"]["impact"]["enum"])
        except (OSError, json.JSONDecodeError, KeyError) as err:
            raise ValueError(
                f"Failed to load suggestion schema from {SCHEMA_PATH}: {err}"
            ) from err
else:
    ALLOWED_CATEGORIES = {"Clarity", "Brevity", "Flow", "Tone", "Grammar", "Structure"}
    ALLOWED_IMPACTS = {"Major", "Minor", "Nit"}

PROSE_EXTENSIONS = {".md", ".markdown", ".rst", ".txt", ".tex", ".adoc"}


def is_prose_file(file_path: str | Path) -> bool:
    """Return True if file path has a supported prose/markup extension."""
    suffix = Path(file_path).suffix.lower()
    return suffix in PROSE_EXTENSIONS


def _scan_code_fences(
    text: str,
) -> tuple[List[tuple[int, int]], List[tuple[int, str]]]:
    """Scan text for closed code fence spans and unclosed opening fences.

    Returns:
        (closed_spans, unclosed_fences) where:
        - closed_spans: list of (start_idx, end_idx) for properly matched fences.
        - unclosed_fences: list of (start_idx, fence_token) for unclosed opening fences.
    """
    fence_pattern = re.compile(
        r"^[ \t]*(?:>[ \t]*)*(```+|~~~+)[^\r\n]*\r?$",
        re.MULTILINE,
    )
    lines = list(fence_pattern.finditer(text))
    closed_spans: List[tuple[int, int]] = []
    unclosed_fences: List[tuple[int, str]] = []

    i = 0
    while i < len(lines):
        open_match = lines[i]
        fence_token = open_match.group(1)
        fence_char = fence_token[0]  # ` or ~
        fence_len = len(fence_token)

        close_found = False
        for j in range(i + 1, len(lines)):
            close_match = lines[j]
            close_token = close_match.group(1)
            # Closing fence must use same character and have length >= opening fence
            if close_token[0] == fence_char and len(close_token) >= fence_len:
                closed_spans.append((open_match.start(), close_match.end()))
                i = j + 1
                close_found = True
                break
        if not close_found:
            unclosed_fences.append((open_match.start(), fence_token))
            i += 1
    return closed_spans, unclosed_fences


def _get_code_fence_spans(text: str, strict: bool = False) -> List[tuple[int, int]]:
    """Return start and end spans of fenced code blocks (supporting indentation and blockquotes)."""
    closed_spans, unclosed_fences = _scan_code_fences(text)
    if unclosed_fences:
        if strict:
            start_idx, token = unclosed_fences[0]
            raise ValueError(
                f"Unterminated code fence '{token}' at character index {start_idx} "
                "— cannot reliably locate suggestion cards"
            )
        # For non-strict callers (e.g. extract_protected_blocks), fail closed to EOF
        for start_idx, _ in unclosed_fences:
            closed_spans.append((start_idx, len(text)))
    return closed_spans


def extract_protected_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract syntax and structural blocks that must be preserved verbatim in prose."""
    protected: List[Dict[str, Any]] = []

    # 1. YAML frontmatter (^---\n[\s\S]*?\n---)
    frontmatter_match = re.match(r"^---\r?\n[\s\S]*?\r?\n---", text)
    if frontmatter_match:
        protected.append(
            {
                "type": "frontmatter",
                "content": frontmatter_match.group(0),
                "span": frontmatter_match.span(),
            }
        )

    # 2. Fenced code blocks (reusing shared fence scanner, fails closed to EOF)
    for start, end in _get_code_fence_spans(text, strict=False):
        block_text = text[start:end]
        if block_text.strip():
            protected.append(
                {"type": "code_block", "content": block_text, "span": (start, end)}
            )

    # 3. LaTeX math blocks ($$ ... $$, fail-closed to EOF)
    for match in re.finditer(r"\$\$[\s\S]*?(?:\$\$|$)", text):
        if match.group(0).strip():
            protected.append(
                {"type": "math_block", "content": match.group(0), "span": match.span()}
            )

    # 4. Alert callouts (> [!NOTE], > [!WARNING], etc.)
    for match in re.finditer(
        r"^>[ \t]*\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][^\n]*", text, re.MULTILINE
    ):
        protected.append(
            {"type": "callout_alert", "content": match.group(0), "span": match.span()}
        )

    # 5. Markdown tables (| header | ... |, handles tables at EOF without trailing newline)
    for match in re.finditer(r"(?:^\|[^\n]+\|\r?\n?){2,}", text, re.MULTILINE):
        protected.append(
            {"type": "table", "content": match.group(0), "span": match.span()}
        )

    # 6. Task list items (- [ ] / - [x])
    for match in re.finditer(r"^[ \t]*-[ \t]+\[[ xX]\][^\n]*", text, re.MULTILINE):
        protected.append(
            {"type": "task_list_item", "content": match.group(0), "span": match.span()}
        )

    # 7. Footnote definitions ([^1]: ...) and references ([^1])
    for match in re.finditer(r"^\[\^[a-zA-Z0-9_-]+\]:[^\n]*", text, re.MULTILINE):
        protected.append(
            {"type": "footnote_def", "content": match.group(0), "span": match.span()}
        )
    for match in re.finditer(r"\[\^[a-zA-Z0-9_-]+\](?!:)", text):
        protected.append(
            {"type": "footnote_ref", "content": match.group(0), "span": match.span()}
        )

    # 8. Inline code (`...`)
    for match in re.finditer(r"`[^`\r\n]+`", text):
        protected.append(
            {"type": "inline_code", "content": match.group(0), "span": match.span()}
        )

    # 9. Inline math ($...$, non-currency: non-whitespace boundaries, excludes comma-formatted currency)
    for match in re.finditer(
        r"(?<![\$\w])\$(?!\s)(?!\d{1,3}(?:,\d{3})+(?:\.\d+)?\$)(?:[^\$\r\n]|\\\$)+?(?<!\s|\$)\$(?![\$\w])",
        text,
    ):
        protected.append(
            {"type": "inline_math", "content": match.group(0), "span": match.span()}
        )

    # 10. HTML tags (<tag> ... </tag> or <tag/>)
    for match in re.finditer(r"<[a-zA-Z/][^>\r\n]*>", text):
        protected.append(
            {"type": "html_tag", "content": match.group(0), "span": match.span()}
        )

    # 11. Markdown link targets / URLs ([text](url) or raw http://)
    for match in re.finditer(r"\[[^\]]+\]\([^)]+\)|https?://[^\s\)]+", text):
        protected.append(
            {"type": "link_url", "content": match.group(0), "span": match.span()}
        )

    return protected


def _extract_quoted_field(field_name: str, body: str, card_id: int) -> str:
    """Extract a quoted field value supporting multiline text, trailing whitespace, and curly quotes."""
    # Matches - **Field:** ["“]...["”][optional whitespace]$
    # Negative lookahead (?!\n-\s+\*\*) ensures quote does not bleed into subsequent field definitions
    pattern = re.compile(
        r"^-\s+\*\*"
        + re.escape(field_name)
        + r":\*\*\s*[\"“]((?:(?!\n-\s+\*\*)[\s\S])*?)[\"”]\s*$",
        re.MULTILINE,
    )
    match = pattern.search(body)
    if match:
        return match.group(1)

    # Check if field header was declared but quote was unterminated / malformed
    header_pattern = re.compile(
        r"^-\s+\*\*" + re.escape(field_name) + r":\*\*", re.MULTILINE
    )
    if header_pattern.search(body):
        raise ValueError(
            f"Unterminated or malformed quoted '{field_name}' in Suggestion #{card_id}"
        )

    raise ValueError(f"Missing required field '{field_name}' in Suggestion #{card_id}")


def _extract_diff_field(
    body: str, card_id: int, body_abs_offset: int = 0
) -> tuple[str | None, tuple[int, int] | None]:
    """Extract optional fenced diff block from suggestion card body.

    Returns:
        (diff_text, (abs_start, abs_end)) or (None, None) if not present.
    """
    diff_header_pattern = re.compile(r"^-\s+\*\*Diff:\*\*[^\r\n]*\r?\n", re.MULTILINE)
    diff_header_match = diff_header_pattern.search(body)
    if not diff_header_match:
        return None, None

    sub_body = body[diff_header_match.end() :]
    # Opening fence: ``` or ~~~, optional blockquote prefixes, optional info string (e.g. diff, Diff, DIFF)
    open_fence_pattern = re.compile(
        r"^[ \t]*(?:>[ \t]*)*(```+|~~~+)[ \t]*(?:[a-zA-Z0-9_-]+)?[ \t]*\r?$",
        re.MULTILINE,
    )
    open_match = open_fence_pattern.search(sub_body)
    if not open_match:
        raise ValueError(
            f"Unterminated or malformed Diff block in Suggestion #{card_id}"
        )

    # Verify only whitespace exists between - **Diff:** line and opening fence
    if sub_body[: open_match.start()].strip() != "":
        raise ValueError(
            f"Unterminated or malformed Diff block in Suggestion #{card_id}"
        )

    fence_token = open_match.group(1)
    fence_char = fence_token[0]
    fence_len = len(fence_token)

    # The closing fence MUST appear before the next known card field (e.g. - **Rationale:**)
    # ponytail: An unindented diff content line deleting a known field at column 0 (e.g. - **Rationale:** old)
    # will bound the search and fail closed. Indented diff blocks (per SKILL.md template) avoid this heuristic limit.
    next_field_pattern = re.compile(
        r"^-\s+\*\*(?:Anchor|Original|Proposed|Diff|Rationale):\*\*", re.MULTILINE
    )
    next_field_match = next_field_pattern.search(sub_body[open_match.end() :])
    max_search_pos = (
        next_field_match.start()
        if next_field_match
        else len(sub_body) - open_match.end()
    )

    diff_content_and_close = sub_body[
        open_match.end() : open_match.end() + max_search_pos
    ]

    close_fence_pattern = re.compile(
        r"^[ \t]*(?:>[ \t]*)*(```+|~~~+)[ \t]*\r?$",
        re.MULTILINE,
    )
    close_matches = list(close_fence_pattern.finditer(diff_content_and_close))
    close_found = None
    for cm in close_matches:
        c_token = cm.group(1)
        if c_token[0] == fence_char and len(c_token) >= fence_len:
            close_found = cm
            break

    if not close_found:
        raise ValueError(
            f"Unterminated or malformed Diff block in Suggestion #{card_id}"
        )

    full_diff_fence = sub_body[
        open_match.start() : open_match.end() + close_found.end()
    ]
    abs_start = body_abs_offset + diff_header_match.end() + open_match.start()
    abs_end = (
        body_abs_offset + diff_header_match.end() + open_match.end() + close_found.end()
    )
    return full_diff_fence.strip(), (abs_start, abs_end)


def parse_suggestion_cards(text: str) -> List[Dict[str, Any]]:
    """Parse markdown suggestion cards into structured dicts with strict schema validation."""
    closed_spans, unclosed_fences = _scan_code_fences(text)

    def is_inside_code(pos: int) -> bool:
        return any(start <= pos < end for start, end in closed_spans)

    card_header_pattern = re.compile(
        r"^###\s+Suggestion\s+#(\d+)\s+`\[([a-zA-Z]+)\]`\s+`\[([a-zA-Z]+)\]`\s*$",
        re.MULTILINE,
    )
    all_card_headers = list(card_header_pattern.finditer(text))
    matches = [m for m in all_card_headers if not is_inside_code(m.start())]

    # Guard 1: Detect if all suggestion headers are trapped inside an outer fenced code block
    if len(all_card_headers) > 0 and len(matches) == 0:
        raise ValueError(
            f"{len(all_card_headers)} suggestion header(s) found but all are inside fenced code blocks "
            "— emit suggestion cards as top-level markdown, not wrapped in code fences"
        )

    # Guard 2: Handle unclosed fences (fail-closed)
    if unclosed_fences:
        # Check if there is only a single unclosed fence and it belongs specifically to a Diff block
        # whose card parser will raise an exact 'Unterminated or malformed Diff block' error.
        diff_unclosed = False
        if len(unclosed_fences) == 1 and len(matches) > 0:
            fence_pos, _ = unclosed_fences[0]
            for idx, ch in enumerate(matches):
                card_start = ch.start()
                card_end = (
                    matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                )
                if card_start <= fence_pos < card_end:
                    card_body = text[ch.end() : card_end]
                    diff_match = re.search(
                        r"^-\s+\*\*Diff:\*\*[^\r\n]*\r?\n", card_body, re.MULTILINE
                    )
                    if diff_match:
                        diff_hdr_abs = ch.end() + diff_match.end()
                        if (
                            diff_hdr_abs <= fence_pos
                            and text[diff_hdr_abs:fence_pos].strip() == ""
                        ):
                            diff_unclosed = True
                            break

        if not diff_unclosed:
            start_idx, token = unclosed_fences[0]
            raise ValueError(
                f"Unterminated code fence '{token}' at character index {start_idx} "
                "— cannot reliably locate suggestion cards"
            )

    # Guard 3: Detect any malformed suggestion headers outside fenced code blocks
    for line_match in re.finditer(r"^###\s*Suggestion[^\r\n]*", text, re.MULTILINE):
        if is_inside_code(line_match.start()):
            continue
        trimmed = line_match.group(0).strip()
        valid_header = re.match(
            r"^###\s+Suggestion\s+#(\d+)\s+`\[([a-zA-Z]+)\]`\s+`\[([a-zA-Z]+)\]`\s*$",
            trimmed,
        )
        if not valid_header:
            raise ValueError(f"Malformed suggestion header: '{trimmed}'")

    if not matches:
        return []

    cards: List[Dict[str, Any]] = []
    seen_ids = set()
    parsed_diff_spans: List[tuple[int, int]] = []

    for i, match in enumerate(matches):
        card_id = int(match.group(1))
        category = match.group(2)
        impact = match.group(3)

        if card_id <= 0:
            raise ValueError(f"Suggestion ID must be positive (>= 1), got #{card_id}")
        if card_id in seen_ids:
            raise ValueError(f"Duplicate suggestion ID #{card_id}")
        seen_ids.add(card_id)

        if category not in ALLOWED_CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. Allowed: {sorted(ALLOWED_CATEGORIES)}"
            )
        if impact not in ALLOWED_IMPACTS:
            raise ValueError(
                f"Invalid impact '{impact}'. Allowed: {sorted(ALLOWED_IMPACTS)}"
            )

        # Slice body content until next card header or EOF
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start_pos:end_pos]

        anchor_match = re.search(r"^-\s+\*\*Anchor:\*\*\s*(.+)$", body, re.MULTILINE)
        if not anchor_match:
            raise ValueError(
                f"Missing required field 'Anchor' in Suggestion #{card_id}"
            )

        original_val = _extract_quoted_field("Original", body, card_id)
        proposed_val = _extract_quoted_field("Proposed", body, card_id)

        rationale_match = re.search(
            r"^-\s+\*\*Rationale:\*\*\s*(.+)$", body, re.MULTILINE
        )
        if not rationale_match:
            raise ValueError(
                f"Missing required field 'Rationale' in Suggestion #{card_id}"
            )

        if original_val == proposed_val:
            raise ValueError(
                f"No-op suggestion in Suggestion #{card_id}: Original and Proposed are identical"
            )

        diff_val, diff_span = _extract_diff_field(
            body, card_id, body_abs_offset=start_pos
        )

        card_dict: Dict[str, Any] = {
            "id": card_id,
            "category": category,
            "impact": impact,
            "anchor": anchor_match.group(1).strip(),
            "original": original_val,
            "proposed": proposed_val,
            "rationale": rationale_match.group(1).strip(),
        }
        if diff_val is not None and diff_span is not None:
            card_dict["diff"] = diff_val
            parsed_diff_spans.append(diff_span)

        cards.append(card_dict)

    # Guard 4: Detect partially trapped card headers outside valid diff blocks
    trapped_headers = []
    for h in all_card_headers:
        if is_inside_code(h.start()):
            in_valid_diff = any(
                d_start <= h.start() < d_end for d_start, d_end in parsed_diff_spans
            )
            if not in_valid_diff:
                trapped_headers.append(h)

    if trapped_headers:
        raise ValueError(
            f"{len(trapped_headers)} suggestion header(s) trapped inside fenced code blocks "
            "— emit suggestion cards as top-level markdown, not wrapped in code fences"
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
            raise ValueError(
                f"Verbatim quote mismatch for Suggestion #{card_id}: original text was not found in source"
            )
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


def main() -> None:
    """CLI entry point to validate suggestion cards and source text."""
    parser = argparse.ArgumentParser(
        description="Validate prose suggestion cards and verify verbatim quote fidelity."
    )
    parser.add_argument(
        "file", help="Path to markdown/prose review file containing suggestion cards"
    )
    parser.add_argument(
        "--source",
        "-s",
        help="Optional source document path for verbatim quote validation",
    )
    parser.add_argument(
        "--require-cards",
        action="store_true",
        help="Fail with non-zero exit code if 0 suggestion cards are found (useful when validating review outputs).",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: Review file not found at {file_path}", file=sys.stderr)
        sys.exit(1)

    content = file_path.read_text(encoding="utf-8")
    try:
        cards = parse_suggestion_cards(content)
        if len(cards) == 0:
            if args.require_cards:
                print(
                    f"Error: No valid suggestion cards found in {file_path} (--require-cards set)",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(
                f"Validation successful: Clean document (0 suggestion cards) in {file_path}."
            )
            sys.exit(0)

        if args.source:
            source_path = Path(args.source)
            if not source_path.exists():
                print(f"Error: Source file not found at {source_path}", file=sys.stderr)
                sys.exit(1)
            source_text = source_path.read_text(encoding="utf-8")
            validate_verbatim_quotes(cards, source_text)
        print(f"Validation successful: {len(cards)} valid suggestion card(s) verified.")
    except Exception as err:
        print(f"Validation failed: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
