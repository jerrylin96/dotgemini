---
name: prose-editor
description: Maps to /edit-prose (or /prose). Use when the user asks to edit, proofread, or review prose, technical documentation, papers, or markdown essays using atomic suggestion cards.
---

# Prose Editor (`/edit-prose`)

The `prose-editor` skill provides structured, granular editing feedback on prose, technical documentation, academic papers, and markdown essays. It solves the visual noise of git diffs on soft-wrapped paragraphs by presenting atomic, easily reviewable **Suggestion Cards**.

## Command Triggers
* `/edit-prose [file_path]` — Run structured review on the specified file.
* `/edit-prose --diff` — Run structured review on modified prose files in the active git changeset.
* `/edit-prose --unslop [file_path]` — Strip AI writing tells from external docs, papers, or PR prose (composable with `--line-edit`).
* `/prose [text_snippet]` — Review provided text snippet directly.

---

## Core Principles

1. **Atomic Suggestion Cards**: Every edit is isolated into a single card with an anchor, verbatim original quote, proposed revision, and explicit rationale.
2. **Strict Verbatim Fidelity**: The `Original` field must match the source text byte-for-byte. Paraphrasing or hallucinating original quotes is strictly forbidden.
3. **Advisory-Only Workflow**: The editor operates in pure advisory mode. Source files are never modified automatically during a review pass.
4. **Token Efficiency (Caveman & Ponytail)**: Rationales are concise, direct, and free of conversational fluff. Avoid unrequested structural rewrites when simple line edits suffice.
5. **Surface Precedence (`--unslop` vs. `caveman`)**: `--unslop` governs the edited external document or PR text; `caveman` governs the agent's chat responses and suggestion rationales; neither applies to the other's surface.

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
* **Unslop (`--unslop`, standalone or composable with `--line-edit`)**:
  - **Content & Language**: Cut superficial `-ing` phrases ("highlighting...", "ensuring..."), vague attributions, **AI vocabulary** (*delve, crucial, interplay, landscape, pivotal, showcase, tapestry, testament, underscore, vibrant, foster, garner*), fancy "is" (*serves as, stands as, boasts*), "Not just X, but Y", forced rule of three, synonym cycling, and false ranges ("from X to Y").
  - **Style & Artifacts**: Avoid **Em dash** punctuation (use periods or commas), mid-sentence colon overuse, boldface overuse, inline-header list tells (`**Performance:** Performance improved...`), title-case headings, decorative emojis, curly quotes, chatbot/sycophantic phrases, filler phrases ("In order to" -> "To"), excessive hedging, and generic conclusions.
  - **Jargon & Plain Speech**: Replace **Abstract metaphor nouns** (*substrate, wedge, vector, locus, nexus, primitive, harness-as-metaphor, surface, bedrock, scaffolding, paradigm, flywheel*) with concrete terms; state mechanism or number instead of how it feels; prefer active voice, strong verbs over adverbs, plain words (`use` over `utilize`/`leverage`), literal phrasing over mannered prose, and avoid **Over-compression** (write complete sentences with articles and verbs in external docs/PRs).

---

## Suggestion Card Schema

Every proposed edit must be formatted as an atomic card adhering to [suggestion_schema.json](resources/suggestion_schema.json):

````markdown
### Suggestion #<ID> `[<Category>]` `[<Impact>]`
- **Anchor:** `<Section or Heading>` (Lines `<Start>-<End>` if applicable)
- **Original:** "<exact verbatim source snippet>"
- **Proposed:** "<clean revised snippet>"
- **Diff:** (Optional)
  ```diff
  - <deleted text or words>
  + <added text or words>
  ```
- **Rationale:** <Direct, token-efficient justification>
````

### Schema Rules & Allowed Enums
* **`Category`**: One of `[Clarity]`, `[Brevity]`, `[Flow]`, `[Tone]`, `[Grammar]`, `[Structure]`.
* **`Impact`**: One of `[Major]` (meaning or structure shift), `[Minor]` (phrasing polish), `[Nit]` (punctuation/typo).
* **`Anchor`**: Indicates where the edit belongs (e.g., `## Architecture Overview` or `Paragraph 3`).
* **`Original`**: Quoted exact substring from the document.
* **`Proposed`**: The replacement text (must differ from `Original`).
* **`Diff`**: Optional fenced ` ```diff ... ``` ` block providing visual color highlighting in terminal CLIs and markdown renderers. If the `**Diff:**` field header is present, the fenced block is required; omit the entire field when no diff is needed. Diff content lines should carry a `+`/`-`/space prefix. Note: The Diff block is visual-only and is not programmatically checked against `Original`/`Proposed`.
* **`Rationale`**: Brief explanation of the improvement (e.g. "Eliminates passive filler", "Clarifies causal sequence").
* **Card IDs**: Strictly positive, unique integers (`#1`, `#2`, `#3`...). When analyzing documents across multiple chunks, IDs remain unique across sections (e.g. chunk 2 starting at `#5`).

---

## Syntax & Structure Preservation

The following non-prose and structural elements must be protected and preserved verbatim unless the user explicitly requests syntax corrections:

* **YAML frontmatter** (`--- ... ---`)
* **Code blocks** (fenced with ``` or ~~~, including indented list blocks and blockquoted fences `> ```python`) and inline code (`` `code` ``)
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
   - CLI: `python3 skills/prose-editor/resources/validator.py <review_file> [--source <source_file>] [--require-cards]`
     - Exits 0 on valid cards or clean document (0 cards).
     - With `--require-cards`, exits 1 if 0 cards are parsed.
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
