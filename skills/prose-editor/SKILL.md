---
name: prose-editor
description: Maps to /edit-prose (or /prose). Use when the user asks to edit, proofread, or review prose, technical documentation, papers, or markdown essays using atomic suggestion cards.
---

# Prose Editor (`/edit-prose`)

The `prose-editor` skill provides structured, granular editing feedback on prose, technical documentation, academic papers, and markdown essays. It solves the visual noise of git diffs on soft-wrapped paragraphs by presenting atomic, easily reviewable **Suggestion Cards**.

## Command Triggers
* `/edit-prose [file_path]` — Run structured review on the specified file.
* `/edit-prose --diff` — Run structured review on modified prose files in the active git changeset.
* `/prose [text_snippet]` — Review provided text snippet directly.

---

## Core Principles

1. **Atomic Suggestion Cards**: Every edit is isolated into a single card with an anchor, verbatim original quote, proposed revision, and explicit rationale.
2. **Strict Verbatim Fidelity**: The `Original` field must match the source text byte-for-byte. Paraphrasing or hallucinating original quotes is strictly forbidden.
3. **Advisory-Only Workflow**: The editor operates in pure advisory mode. Source files are never modified automatically during a review pass.
4. **Token Efficiency (Caveman & Ponytail)**: Rationales are concise, direct, and free of conversational fluff. Avoid unrequested structural rewrites when simple line edits suffice.

---

## Editing Tiers

Select an editing tier based on user goals or flags:

* **Proofread (`--proofread`)**:
  - Mechanics and correctness only: spelling, punctuation, capitalization, obvious typos, subject-verb agreement.
  - Leaves sentence structure, tone, rhythm, and authorial voice completely untouched.
* **Line Edit (`--line-edit`, Default)**:
  - Sentence-level craft: cadence, rhythm, conciseness, removing passive padding, sharpening verbs, untangling ambiguous syntax.
  - Preserves core meaning, paragraph structure, and authorial voice.
* **Developmental / Structural (`--developmental`)**:
  - Macro-level structure: argument flow, paragraph order, section transitions, redundant content identification, missing foundational context.

---

## Suggestion Card Schema

Every proposed edit must be formatted as an atomic card adhering to [suggestion_schema.json](resources/suggestion_schema.json):

```markdown
### Suggestion #<ID> `[<Category>]` `[<Impact>]`
- **Anchor:** `<Section or Heading>` (Lines `<Start>-<End>` if applicable)
- **Original:** "<exact verbatim source snippet>"
- **Proposed:** "<clean revised snippet>"
- **Rationale:** <Direct, token-efficient justification>
```

### Schema Rules & Allowed Enums
* **`Category`**: One of `[Clarity]`, `[Brevity]`, `[Flow]`, `[Tone]`, `[Grammar]`, `[Structure]`.
* **`Impact`**: One of `[Major]` (meaning or structure shift), `[Minor]` (phrasing polish), `[Nit]` (punctuation/typo).
* **`Anchor`**: Indicates where the edit belongs (e.g., `## Architecture Overview` or `Paragraph 3`).
* **`Original`**: Quoted exact substring from the document.
* **`Proposed`**: The replacement text (must differ from `Original`).
* **`Rationale`**: Brief explanation of the improvement (e.g. "Eliminates passive filler", "Clarifies causal sequence").
* **Card IDs**: Strictly positive, unique integers (`#1`, `#2`, `#3`...). When analyzing documents across multiple chunks, IDs remain unique across sections (e.g. chunk 2 starting at `#5`).

---

## Syntax & Structure Preservation

The following non-prose and structural elements must be protected and preserved verbatim unless the user explicitly requests syntax corrections:

* **YAML frontmatter** (`--- ... ---`)
* **Code blocks** (fenced with ``` or ~~~) and inline code (`` `code` ``)
* **LaTeX math blocks** (`$$...$$`) and inline math (`$...$`)
* **Markdown tables** (`| col1 | col2 |`)
* **Alert callouts** (`> [!NOTE]`, `> [!WARNING]`, `> [!TIP]`, etc.)
* **Task lists** (`- [ ]`, `- [x]`) and standard lists
* **Footnotes** (`[^1]` and `[^1]: ...`)
* **HTML tags**, raw URLs, and markdown link targets

---

## Validation & Tooling

To ensure schema compliance and verbatim quote fidelity, validate generated suggestions using the bundled resources:

1. **Schema Reference**: Ensure all suggestion attributes match [resources/suggestion_schema.json](resources/suggestion_schema.json).
2. **Runtime Verification**: Import or run `resources/validator.py`:
   - CLI: `python3 skills/prose-editor/resources/validator.py <review_file> --source <source_file>`
   - `parse_suggestion_cards(text)`: Verifies card syntax, positive unique IDs, and valid schema enums.
   - `validate_verbatim_quotes(cards, source_text)`: Guarantees that every `Original` quote exists verbatim and unambiguously in the source document.
   - `extract_protected_blocks(text)`: Inspects protected code, math, table, and callout regions.

---

## Large Document Chunking

For documents exceeding **3,000 words** or **200 lines**:
1. Split analysis into logical chunks based on top-level markdown headings (`#`, `##`).
2. Process and output suggestion cards section-by-section.
3. Maintain global sequential card IDs across all sections (`#1`, `#2`, `#3`...).
4. Prevent context drift and token cutoff by summarizing each section before proceeding to the next.

---

## Diff Mode Filtering

When invoked with `--diff` (or when inspecting branch changes):
* **Prose Whitelist**: Only parse files matching `.md`, `.markdown`, `.rst`, `.txt`, `.tex`, or `.adoc`.
* **Auto-Skip**: Automatically ignore code files (`.py`, `.js`, `.go`, etc.), configuration/data files (`.json`, `.yaml`, `.toml`, lockfiles), and binary files.

---

## Clean Document State

When a document meets high polish standards with **0 actionable suggestions**, output a clean executive summary:

```markdown
### Prose Review Summary: Clean Document
- **Total Suggestions:** 0
- **Document Length:** <N> words (~<M> min read)
- **Status:** Clean prose with consistent voice and strong structural flow; No edits recommended.
```

---

## Review Executive Summary Template

For reviews with findings, prepend the output with an executive summary table:

```markdown
### Prose Review Summary
- **Document:** `<file_path>`
- **Total Suggestions:** <Count> (Major: <X>, Minor: <Y>, Nit: <Z>)
- **Breakdown by Category:** Clarity (<A>), Brevity (<B>), Flow (<C>), Tone (<D>), Grammar (<E>), Structure (<F>)
- **Word Delta:** <±Delta> words (<±Percent>%)
- **Editorial Assessment:** <1-2 terse sentences evaluating overall prose quality and focus areas.>
```
