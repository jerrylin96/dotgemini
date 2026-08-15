import importlib.util
import json
from pathlib import Path
import re
import pytest

WORKTREE_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = WORKTREE_ROOT / "skills" / "prose-editor"
SKILL_FILE = SKILL_DIR / "SKILL.md"
VALIDATOR_PATH = SKILL_DIR / "resources" / "validator.py"
SCHEMA_PATH = SKILL_DIR / "resources" / "suggestion_schema.json"


def get_validator():
    """Dynamically load validator module from resources directory."""
    if not VALIDATOR_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("prose_editor_validator", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        return None
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    return validator


def test_skill_metadata_and_frontmatter():
    """Verify that SKILL.md exists and contains valid YAML frontmatter and required sections."""
    assert SKILL_FILE.exists(), f"SKILL.md not found at {SKILL_FILE}"
    content = SKILL_FILE.read_text(encoding="utf-8")

    # Check frontmatter
    assert content.startswith("---\n"), "SKILL.md must start with YAML frontmatter delimiter '---'"
    frontmatter_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    assert frontmatter_match is not None, "Missing closing YAML frontmatter delimiter"
    frontmatter = frontmatter_match.group(1)

    assert "name: prose-editor" in frontmatter, "Frontmatter must define name: prose-editor"
    assert "description:" in frontmatter, "Frontmatter must define a description"
    assert "/edit-prose" in frontmatter, "Frontmatter description must mention command trigger /edit-prose"

    # Check core section headings
    required_sections = [
        "## Command Triggers",
        "## Core Principles",
        "## Editing Tiers",
        "## Suggestion Card Schema",
        "## Syntax & Structure Preservation",
        "## Validation & Tooling",
        "## Large Document Chunking",
        "## Diff Mode Filtering",
        "## Clean Document State",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section '{section}' in SKILL.md"


def test_enum_source_of_truth_sync():
    """Assert that category and impact enums stay synchronized across schema, validator, and docs."""
    validator = get_validator()
    assert validator is not None, "Validator module not loaded"
    assert SCHEMA_PATH.exists(), f"Schema file not found at {SCHEMA_PATH}"

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)

    schema_categories = set(schema["properties"]["category"]["enum"])
    schema_impacts = set(schema["properties"]["impact"]["enum"])

    assert validator.ALLOWED_CATEGORIES == schema_categories
    assert validator.ALLOWED_IMPACTS == schema_impacts

    skill_text = SKILL_FILE.read_text(encoding="utf-8")
    for cat in schema_categories:
        assert f"`[{cat}]`" in skill_text or cat in skill_text
    for imp in schema_impacts:
        assert f"`[{imp}]`" in skill_text or imp in skill_text


def test_suggestion_card_format_validator():
    """Verify suggestion card parsing and validation against allowed schema, including negative cases."""
    validator = get_validator()
    assert validator is not None, "Validator module not implemented yet"

    valid_card_text = """### Suggestion #1 `[Brevity]` `[Minor]`
- **Anchor:** `Introduction` (Lines 10-12)
- **Original:** "It is important to note that the primary function of this module is"
- **Proposed:** "This module primarily serves to"
- **Rationale:** Removes unnecessary filler and passive padding.

### Suggestion #2 `[Clarity]` `[Major]`
- **Anchor:** `Section 2` (Lines 30-35)
- **Original:** "The system may potentially experience degraded performance if overloaded."
- **Proposed:** "Overloading the system degrades performance."
- **Rationale:** Tightens active voice and clarifies causal outcome.
"""
    cards = validator.parse_suggestion_cards(valid_card_text)
    assert len(cards) == 2

    card1 = cards[0]
    assert card1["id"] == 1
    assert card1["category"] == "Brevity"
    assert card1["impact"] == "Minor"
    assert card1["anchor"] == "`Introduction` (Lines 10-12)"
    assert card1["original"] == "It is important to note that the primary function of this module is"
    assert card1["proposed"] == "This module primarily serves to"
    assert "filler" in card1["rationale"]

    card2 = cards[1]
    assert card2["id"] == 2
    assert card2["category"] == "Clarity"
    assert card2["impact"] == "Major"

    assert card1["category"] in validator.ALLOWED_CATEGORIES
    assert card1["impact"] in validator.ALLOWED_IMPACTS


def test_parser_quote_edge_cases():
    """Verify trailing space handling, multiline quotes, and curly quotes in parser."""
    validator = get_validator()
    assert validator is not None, "Validator module not loaded"

    # Trailing space after closing quote
    trailing_space_card = (
        "### Suggestion #1 `[Brevity]` `[Minor]`\n"
        "- **Anchor:** `Intro`\n"
        '- **Original:** "The primary function of this module is"   \n'
        '- **Proposed:** "This module functions to"   \n'
        "- **Rationale:** Brevity.\n"
    )
    cards = validator.parse_suggestion_cards(trailing_space_card)
    assert len(cards) == 1
    assert cards[0]["original"] == "The primary function of this module is"
    assert cards[0]["proposed"] == "This module functions to"

    # Curly quotes
    curly_card = (
        "### Suggestion #1 `[Clarity]` `[Minor]`\n"
        "- **Anchor:** `Intro`\n"
        "- **Original:** “The primary function of this module is”\n"
        "- **Proposed:** “This module functions to”\n"
        "- **Rationale:** Clarity.\n"
    )
    curly_parsed = validator.parse_suggestion_cards(curly_card)
    assert len(curly_parsed) == 1
    assert curly_parsed[0]["original"] == "The primary function of this module is"

    # Multiline quotes
    multiline_card = (
        "### Suggestion #1 `[Flow]` `[Major]`\n"
        "- **Anchor:** `Section 1`\n"
        '- **Original:** "First paragraph sentence.\nSecond paragraph sentence."\n'
        '- **Proposed:** "Combined fluid sentence."\n'
        "- **Rationale:** Flow improvement.\n"
    )
    multi_parsed = validator.parse_suggestion_cards(multiline_card)
    assert len(multi_parsed) == 1
    assert multi_parsed[0]["original"] == "First paragraph sentence.\nSecond paragraph sentence."

    # Unterminated quote raises ValueError
    unterminated_card = (
        "### Suggestion #1 `[Brevity]` `[Minor]`\n"
        "- **Anchor:** `Intro`\n"
        '- **Original:** "Unterminated quote without closing\n'
        '- **Proposed:** "Valid"\n'
        "- **Rationale:** Test.\n"
    )
    with pytest.raises(ValueError, match="Unterminated or malformed quoted 'Original'"):
        validator.parse_suggestion_cards(unterminated_card)


def test_malformed_suggestion_header_rejection():
    """Verify that malformed headers outside code blocks are rejected with ValueError."""
    validator = get_validator()
    assert validator is not None, "Validator module not loaded"

    # Missing impact token
    malformed_header = """### Suggestion #1 `[Clarity]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="Malformed suggestion header"):
        validator.parse_suggestion_cards(malformed_header)

    # Missing ID #
    missing_id_header = """### Suggestion `[Clarity]` `[Minor]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="Malformed suggestion header"):
        validator.parse_suggestion_cards(missing_id_header)


def test_parse_real_skill_md_without_crash():
    """Verify that parsing the skill's own SKILL.md does not crash on template headers in code fences."""
    validator = get_validator()
    assert validator is not None, "Validator module not loaded"

    skill_content = SKILL_FILE.read_text(encoding="utf-8")
    # Should not raise ValueError about malformed template header in code block
    cards = validator.parse_suggestion_cards(skill_content)
    assert isinstance(cards, list)


def test_unclosed_code_fence_rejection():
    """Verify that unclosed code fences raise an error for both column-0 and indented fences."""
    validator = get_validator()
    assert validator is not None, "Validator module not loaded"

    unclosed_doc = """# Review

```python
def example():
    pass

### Suggestion #1 `[Clarity]` `[Major]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="Unterminated code fence"):
        validator.parse_suggestion_cards(unclosed_doc)

    # Unclosed indented code fence inside a list
    unclosed_indented_doc = """1. Step one:

   ```bash
   echo "hello"

### Suggestion #1 `[Clarity]` `[Major]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="Unterminated code fence"):
        validator.parse_suggestion_cards(unclosed_indented_doc)

    # Stray backticks in regular prose should not cause unclosed fence errors
    stray_backtick_doc = """# Review
Here is some `inline code` and another stray ` backtick.

### Suggestion #1 `[Clarity]` `[Major]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz
"""
    cards = validator.parse_suggestion_cards(stray_backtick_doc)
    assert len(cards) == 1
    assert cards[0]["id"] == 1


def test_indented_and_blockquoted_code_fences():
    """Verify that indented and blockquoted code fences are protected."""
    validator = get_validator()
    assert validator is not None, "Validator module not loaded"

    sample = """1. Run setup:

   ```bash
   rm -rf /var/data && ./setup.sh --force
   ```

2. Configuration:

> ```python
> x = 1
> y = 2
> ```
"""
    protected = validator.extract_protected_blocks(sample)
    code_blocks = [b for b in protected if b["type"] == "code_block"]
    assert len(code_blocks) == 2
    assert any("rm -rf /var/data" in b["content"] for b in code_blocks)
    assert any("x = 1" in b["content"] for b in code_blocks)


def test_card_id_sequencing_and_chunking():
    """Verify chunked IDs starting at #5, filtered sets #1/#3, and rejection of duplicates / #0."""
    validator = get_validator()
    assert validator is not None, "Validator module not loaded"

    # Chunk starting at #5
    chunk_card = """### Suggestion #5 `[Brevity]` `[Minor]`
- **Anchor:** `Section 5`
- **Original:** "Chunk original"
- **Proposed:** "Chunk proposed"
- **Rationale:** Brevity in chunk 2.

### Suggestion #6 `[Clarity]` `[Minor]`
- **Anchor:** `Section 6`
- **Original:** "Chunk 6 original"
- **Proposed:** "Chunk 6 proposed"
- **Rationale:** Clarity in chunk 2.
"""
    chunk_parsed = validator.parse_suggestion_cards(chunk_card)
    assert len(chunk_parsed) == 2
    assert chunk_parsed[0]["id"] == 5
    assert chunk_parsed[1]["id"] == 6

    # Filtered cards #1 and #3 (gap allowed)
    filtered_card = """### Suggestion #1 `[Brevity]` `[Minor]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz

### Suggestion #3 `[Clarity]` `[Minor]`
- **Anchor:** `Section 3`
- **Original:** "alpha"
- **Proposed:** "beta"
- **Rationale:** baz
"""
    filtered_parsed = validator.parse_suggestion_cards(filtered_card)
    assert len(filtered_parsed) == 2
    assert filtered_parsed[0]["id"] == 1
    assert filtered_parsed[1]["id"] == 3

    # Duplicate IDs must still be rejected
    duplicate_id_card = """### Suggestion #1 `[Brevity]` `[Minor]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz

### Suggestion #1 `[Clarity]` `[Minor]`
- **Anchor:** `Intro`
- **Original:** "alpha"
- **Proposed:** "beta"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="Duplicate suggestion ID #1"):
        validator.parse_suggestion_cards(duplicate_id_card)

    # Non-positive ID must be rejected
    zero_id_card = """### Suggestion #0 `[Brevity]` `[Minor]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="Suggestion ID must be positive"):
        validator.parse_suggestion_cards(zero_id_card)

    # No-op edit
    noop_card = """### Suggestion #1 `[Brevity]` `[Minor]`
- **Anchor:** `Intro`
- **Original:** "identical text"
- **Proposed:** "identical text"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="No-op suggestion"):
        validator.parse_suggestion_cards(noop_card)


def test_verbatim_quote_fidelity_and_ambiguity():
    """Ensure proposed cards fail validation if original is not in source, or occurs ambiguously multiple times."""
    validator = get_validator()
    assert validator is not None, "Validator module not implemented yet"

    source_text = """# Architecture Overview\r\nThis module primarily serves to handle incoming event payloads from the client.\r\nAll events are buffered before batch dispatching.\r\n"""

    valid_card = {
        "id": 1,
        "original": "This module primarily serves to handle incoming event payloads from the client.",
        "proposed": "This module handles incoming client event payloads.",
        "category": "Brevity",
        "impact": "Minor",
    }

    invalid_card = {
        "id": 2,
        "original": "This module primarily serves to handle incoming events from the client.",
        "proposed": "This module handles incoming events.",
        "category": "Brevity",
        "impact": "Minor",
    }

    assert validator.validate_verbatim_quotes([valid_card], source_text) is True
    with pytest.raises(ValueError, match="Verbatim quote mismatch for Suggestion #2"):
        validator.validate_verbatim_quotes([invalid_card], source_text)

    # Ambiguous duplicate occurrence test
    duplicate_source = "The system is online. The system is online."
    ambiguous_card = {
        "id": 1,
        "original": "The system is online.",
        "proposed": "The system runs.",
        "category": "Brevity",
        "impact": "Minor",
    }
    with pytest.raises(ValueError, match="Ambiguous verbatim quote for Suggestion #1"):
        validator.validate_verbatim_quotes([ambiguous_card], duplicate_source)


def test_inline_math_vs_currency_isolation():
    """Verify inline math supports digit-leading LaTeX ($2x+1$, $100$) while rejecting currency."""
    validator = get_validator()
    assert validator is not None, "Validator module not loaded"

    # Currency should not match across various formatting styles
    currency_samples = [
        "The migration cost $5,000 in Q1 and the rollback cost $2,000 more, which was over budget.",
        "Total is $5000 vs $9000.",
        "Budget $100 then $200.",
        "Price ranges from $30 to $40.",
        "Estimated at $100-$200 per unit.",
        "Price is $5,000.",
    ]
    for sample in currency_samples:
        protected = validator.extract_protected_blocks(sample)
        math_blocks = [b for b in protected if b["type"] == "inline_math"]
        assert len(math_blocks) == 0, f"Expected 0 inline math blocks in '{sample}', found {math_blocks}"

    # Legitimate digit-leading and command-bearing LaTeX math must match
    math_text = (
        "Here is formula $2x + 1$, mapping $x \\to y$, element $x \\in S$, limit $\\lim_{n \\to \\infty} a_n$, "
        "subscript $v_{in}$, mapping $f \\colon A \\to B$, coefficient $3\\alpha$, and value $100$ alongside $E=mc^2$."
    )
    math_protected = validator.extract_protected_blocks(math_text)
    found_math = [b["content"] for b in math_protected if b["type"] == "inline_math"]
    assert "$2x + 1$" in found_math
    assert "$x \\to y$" in found_math
    assert "$x \\in S$" in found_math
    assert "$\\lim_{n \\to \\infty} a_n$" in found_math
    assert "$v_{in}$" in found_math
    assert "$f \\colon A \\to B$" in found_math
    assert "$3\\alpha$" in found_math
    assert "$100$" in found_math
    assert "$E=mc^2$" in found_math


def test_syntax_preservation_parser():
    """Verify syntax elements like code blocks, math, tables, callouts, task lists, and footnotes are identified."""
    validator = get_validator()
    assert validator is not None, "Validator module not implemented yet"

    sample_doc = """---
title: Sample Doc
author: Test
---

# Document Title

Here is a paragraph of regular prose with footnote[^1] and raw link https://example.com and [markdown link](https://test.org).

```python
def foo():
    return "protected code"
```

~~~bash
echo "tilde fenced code block"
~~~

Another sentence with math block:
$$
\\sigma = \\sqrt{\\frac{1}{N}\\sum_{i=1}^N (x_i - \\mu)^2}
$$
and inline math $E=mc^2$ alongside inline `code_fn()` and <div class="test">HTML</div>.

> [!NOTE]
> Important callout alert content.

| Header 1 | Header 2 |
|---|---|
| Value 1 | Value 2 |

- [ ] Unfinished task item
- [x] Completed task item
- Regular bullet item

[^1]: Footnote definition content."""

    protected = validator.extract_protected_blocks(sample_doc)

    assert any("title: Sample Doc" in block["content"] for block in protected), "YAML frontmatter not protected"
    assert any("def foo():" in block["content"] for block in protected), "Backtick code block not protected"
    assert any("tilde fenced code" in block["content"] for block in protected), "Tilde code block not protected"
    assert any("\\sigma =" in block["content"] for block in protected), "LaTeX math block not protected"
    assert any("E=mc^2" in block["content"] for block in protected), "Inline math not protected"
    assert any("`code_fn()`" in block["content"] for block in protected), "Inline code not protected"
    assert any("<div class=" in block["content"] for block in protected), "HTML tag not protected"
    assert any("[!NOTE]" in block["content"] for block in protected), "Alert callout not protected"
    assert any("Header 1" in block["content"] for block in protected), "Markdown table without EOF newline not protected"
    assert any("- [ ]" in block["content"] for block in protected), "Unchecked task list not protected"
    assert any("- [x]" in block["content"] for block in protected), "Checked task list not protected"
    assert any("[^1]:" in block["content"] for block in protected), "Footnote definition not protected"
    assert any("https://example.com" in block["content"] for block in protected), "Link URL not protected"


def test_diff_prose_extension_filter():
    """Verify that only supported prose/documentation file extensions are allowed."""
    validator = get_validator()
    assert validator is not None, "Validator module not implemented yet"

    prose_files = [
        "README.md",
        "docs/guide.markdown",
        "papers/manuscript.tex",
        "notes/summary.txt",
        "manual/index.rst",
        "spec.adoc",
    ]
    non_prose_files = [
        "src/main.py",
        "package.json",
        "config.yaml",
        "poetry.lock",
        "image.png",
        "binary.bin",
    ]

    for path in prose_files:
        assert validator.is_prose_file(path) is True, f"Expected {path} to be recognized as prose"

    for path in non_prose_files:
        assert validator.is_prose_file(path) is False, f"Expected {path} to be filtered out as non-prose"


def test_zero_finding_clean_state_formatter():
    """Verify that a document with 0 findings generates a clean, structured summary."""
    validator = get_validator()
    assert validator is not None, "Validator module not implemented yet"

    summary = validator.format_clean_summary(total_words=1250, reading_time_min=5)
    assert "**Total Suggestions:** 0" in summary
    assert "1,250 words" in summary
    assert "No edits recommended" in summary
