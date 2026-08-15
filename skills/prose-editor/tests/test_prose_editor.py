import importlib.util
from pathlib import Path
import re
import pytest

WORKTREE_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = WORKTREE_ROOT / "skills" / "prose-editor"
SKILL_FILE = SKILL_DIR / "SKILL.md"
VALIDATOR_PATH = SKILL_DIR / "resources" / "validator.py"


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
    
    # Check core section headings
    required_sections = [
        "## Core Principles",
        "## Editing Tiers",
        "## Suggestion Card Schema",
        "## Syntax & Structure Preservation",
        "## Large Document Chunking",
        "## Diff Mode Filtering",
        "## Clean Document State",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section '{section}' in SKILL.md"


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
    
    # Negative test: Invalid category
    invalid_cat_card = """### Suggestion #3 `[Style]` `[Minor]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="Invalid category"):
        validator.parse_suggestion_cards(invalid_cat_card)

    # Negative test: Invalid impact
    invalid_impact_card = """### Suggestion #4 `[Brevity]` `[Urgent]`
- **Anchor:** `Intro`
- **Original:** "foo"
- **Proposed:** "bar"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="Invalid impact"):
        validator.parse_suggestion_cards(invalid_impact_card)

    # Negative test: Missing required fields
    missing_fields_card = """### Suggestion #5 `[Brevity]` `[Minor]`
- **Anchor:** `Intro`
- **Proposed:** "bar"
- **Rationale:** baz
"""
    with pytest.raises(ValueError, match="Missing required field"):
        validator.parse_suggestion_cards(missing_fields_card)


def test_verbatim_quote_fidelity():
    """Ensure proposed cards fail validation if the original text is not a verbatim substring of source."""
    validator = get_validator()
    assert validator is not None, "Validator module not implemented yet"
    
    source_text = """# Architecture Overview
This module primarily serves to handle incoming event payloads from the client.
All events are buffered before batch dispatching.
"""
    valid_card = {
        "id": 1,
        "original": "This module primarily serves to handle incoming event payloads from the client.",
        "proposed": "This module handles incoming client event payloads.",
        "category": "Brevity",
        "impact": "Minor",
    }
    
    invalid_card = {
        "id": 2,
        "original": "This module primarily serves to handle incoming events from the client.",  # Missing 'payloads'
        "proposed": "This module handles incoming events.",
        "category": "Brevity",
        "impact": "Minor",
    }
    
    assert validator.validate_verbatim_quotes([valid_card], source_text) is True
    with pytest.raises(ValueError, match="Verbatim quote mismatch for Suggestion #2"):
        validator.validate_verbatim_quotes([invalid_card], source_text)


def test_syntax_preservation_parser():
    """Verify syntax elements like code blocks, math, tables, callouts, task lists, and footnotes are identified."""
    validator = get_validator()
    assert validator is not None, "Validator module not implemented yet"
    
    sample_doc = """# Document Title

Here is a paragraph of regular prose with footnote[^1].

```python
def foo():
    return "protected code"
```

Another sentence with math block:
$$
\\sigma = \\sqrt{\\frac{1}{N}\\sum_{i=1}^N (x_i - \\mu)^2}
$$
and inline math $E=mc^2$ alongside inline `code_fn()`.

> [!NOTE]
> Important callout alert content.

| Header 1 | Header 2 |
|---|---|
| Value 1 | Value 2 |

- [ ] Unfinished task item
- [x] Completed task item
- Regular bullet item

[^1]: Footnote definition content.
"""
    protected = validator.extract_protected_blocks(sample_doc)
    
    assert any("def foo():" in block["content"] for block in protected), "Code block not protected"
    assert any("\\sigma =" in block["content"] for block in protected), "LaTeX math block not protected"
    assert any("[!NOTE]" in block["content"] for block in protected), "Alert callout not protected"
    assert any("Header 1" in block["content"] for block in protected), "Markdown table not protected"
    assert any("- [ ]" in block["content"] for block in protected), "Unchecked task list not protected"
    assert any("- [x]" in block["content"] for block in protected), "Checked task list not protected"
    assert any("[^1]:" in block["content"] for block in protected), "Footnote definition not protected"


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
