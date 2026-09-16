# Feature Specification: explain-diff-anti-hallucination

## 1. Background & Problem Statement
During a diff walkthrough of 20 files, an ad-hoc python script dumped hunks directly to terminal stdout via `run_command`, which was truncated (`<truncated 39 lines>`). Instead of retrieving the missing hunk with `view_file` or writing a targeted scratch diff, the agent relied on generative memory to complete a fenced `diff` block for `CITATION.cff`, hallucinating an incorrect author affiliation ("Harvard biostatistics" instead of "Boston University").

Terminal stdout truncation is a silent failure mode across LLM agent workflows: when stdout truncates, the model encounters a gap in its context window and frequently fills the gap by inventing plausible-looking code, diff hunks, line numbers, or metadata tags.

## 2. Goals & Non-Goals
### Goals
- Establish an agent-wide **Verbatim Quotation & Truncation Circuit Breaker** in `AGENTS.md` (§3 Core Operating Behaviors -> Empirical Grounding).
- Explicitly forbid the agent from reciting, paraphrasing, or guessing content from any truncated tool output (`<truncated N lines>`, `<truncated N bytes>`, `stdout_truncated: true`, `observation too long`, or unviewed `view_file` pagination).
- Enforce in `skills/explain-diff/SKILL.md` an explicit prohibition against ad-hoc terminal scripts (`python3 -c`, raw `git diff`) that dump any diff hunks (single-file or multi-file) directly to stdout.
- Mandate mechanical topic diff extraction in `skills/explain-diff/SKILL.md` (§4 Topic-by-Topic Walkthrough Flow): write path-limited scratch diff `temp_topic_diff.txt` with individually quoted pathspecs and inspect it via `view_file` (paginating through EOF) before quoting verbatim in fenced `diff` blocks.
- Forbid emitting any fenced `diff` block without prior `view_file` inspection in the active context.
- Extend fail-closed exit status 0 verification to `temp_topic_diff.txt`.
- Add a dedicated section in `skills/explain-diff/resources/robustness_guide.md` covering **Truncation Handling & Grounded Quotation Invariants**, the incident failure mode, and path-scoped scratch diffs.
- Update `robustness_guide.md` §1 (Tooling Contract), §3 (Roles), and §7 (Cleanup) to include `temp_topic_diff.txt`.
- Expand `skills/explain-diff/tests/test_explain_diff.py` to verify the presence and rigor of all new directives across `AGENTS.md`, `SKILL.md`, and `robustness_guide.md`, including updating `test_root_commit_cross_reference_corrected` and `test_fail_closed_artifact_exit_status_checks`.

### Non-Goals
- Altering the tri-lens menu tokens (`[t]`, `[c]`, `[f]`) or KaTeX notation in `explain-diff`.
- Changing Git diff flags (`--find-renames --find-copies` remains the standard).
- Creating new dependencies or modifying scripts outside the repository.

## 3. Detailed Technical Specifications

### 3.1 Global Agent Guide (`AGENTS.md`)
In §3 *Core Operating Behaviors -> Empirical Grounding (Zero Hallucinated Claims)*:
- Add an explicit **Verbatim Quotation & Truncation Circuit Breaker**:
  - Every fenced `diff` or code block cited as empirical truth MUST be backed byte-for-byte by untruncated tool output or line-numbered `view_file` citations in context.
  - **Truncation Circuit Breaker**: If any tool output indicates truncation (including `<truncated N lines>`, `<truncated N bytes>`, `... output truncated ...`, `observation too long`, `stdout_truncated: true`, or unviewed `view_file` pagination where lines remain in the artifact), the agent is strictly forbidden from reciting, paraphrasing, or guessing any content from the truncated or unviewed region. It MUST either call `view_file` on the source artifact (reading through EOF) or write targeted output to a scratch file and view it.

### 3.2 Skill Specification (`skills/explain-diff/SKILL.md`)
- In §1 (*Get the Diff Safely & Extract Commits*):
  - Add explicit prohibition: Never run ad-hoc terminal scripts (`python3 -c`, raw `git diff`, etc.) that dump diff hunks directly to stdout where terminal truncation occurs. Any diff output (single-file or multi-file) must always be redirected to scratch files and read with `view_file`.
  - Include `temp_topic_diff.txt` in the list of managed scratch files in Execution & Robustness Directives:
    `temp_topic_diff.txt` stores path-limited topic diff hunks for topic walkthroughs.
  - In §1h (*Fail-Closed Artifact & Exit Status Verification*): Extend exit status 0 verification to `temp_topic_diff.txt`. If the command fails, STOP immediately, report Git error output, do not read partial files, and do not emit fenced diff blocks.
- In Context Resolution (Commit mode):
  - Update the root-commit empty-tree two-argument reference list to include Step 4b: `(steps 1c–1f, 4b, 6b)`.
- In §4 (*Topic-by-Topic Walkthrough Flow (`[t]`)*):
  - In subsection 4b (*Verbatim Cross-File Hunks*):
    - Mandate mechanical topic diff extraction before presenting topic hunks:
      - Normal commit/branch range:
        `git diff "<reference_commit_hash>...<commit_hash>" --find-renames --find-copies -- "<file1>" "<file2>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_topic_diff.txt"`
      - Root commit (empty tree `4b825dc642cb6eb9a060e54bf8d69288fbee4904`):
        `git diff "<reference_commit_hash>" "<commit_hash>" --find-renames --find-copies -- "<file1>" "<file2>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_topic_diff.txt"`
      - Note on pathspec quoting: Each file argument must be quoted individually.
      - Note on renames and copies: If a topic contains a renamed or copied file whose source is outside the topic pathspec, pass both source and target paths to the pathspec, or use global metadata from `temp_diff_paths.txt` / `temp_diff_numstat.txt` to emit `[rename: ...]` / `[copy: ...]` metadata tags per §2.
    - Verification and Pagination: The agent MUST verify command exit status 0, calculate the total line count, and iterate `view_file` until `StartLine` > total lines (EOF) in the active topic iteration before quoting verbatim in fenced `diff` blocks.
    - Strict prohibition: Emitting any fenced `diff` block without prior `view_file` inspection in the active context is strictly forbidden.
    - Binary & Metadata Handling: For files where `temp_diff_numstat.txt` reports `-\t-\t` (binary, submodule, symlink, mode change), use metadata tags per §2; do not attempt to render binary diffs in text fenced blocks.

### 3.3 Robustness Guide (`skills/explain-diff/resources/robustness_guide.md`)
- In §1 (*Tooling Contract*):
  - Add `temp_topic_diff.txt` to the enumerated list of primary human-readable text artifacts intended for `view_file`.
- In §3 (*Temporary File Roles*):
  - Document `temp_topic_diff.txt`: Stores path-limited topic diff hunks for topic-by-topic walkthrough (`git diff ... --find-renames --find-copies -- "<file1>" "<file2>" > temp_topic_diff.txt`).
- Add a new dedicated section: **Truncation Handling & Grounded Quotation Invariants**:
  - Document the failure mode of terminal stdout truncation (`<truncated N lines>`, `<truncated N bytes>`, `observation too long`, etc.) during command execution.
  - Explain the hallucination risk: when terminal stdout truncates hunks, LLMs tend to fill the context gap with hallucinated code or metadata from parametric memory.
  - Document the mechanical extraction protocol: redirecting path-limited diffs to `temp_topic_diff.txt`, checking exit status 0, and reading iteratively via `view_file` through EOF (up to 800 lines per turn).
  - Explicitly forbid emitting fenced diff blocks without grounded, untruncated `view_file` reads in active context.
  - Detail binary and metadata tag handling for non-text entries.
- In §7 (*Cleanup*):
  - Ensure `temp_topic_diff.txt` is listed in allowed scratch file deletions.

### 3.4 Test Suite (`skills/explain-diff/tests/test_explain_diff.py`)
Add and update tests using pytest:
1. `test_root_commit_cross_reference_corrected(skill_content)`:
   - Update regex to match updated step references including 4b: `assert re.search(r"steps?\s+1c[–-]1f,\s*(?:4b,\s*)?6b", skill_content)`.
2. `test_fail_closed_artifact_exit_status_checks(skill_content)`:
   - Add assertion that `temp_topic_diff.txt` is included in the fail-closed exit status check list.
3. `test_truncation_circuit_breaker_in_agents_md(agents_content)`:
   - Verifies `AGENTS.md` defines the truncation circuit breaker covering truncation signals (`<truncated`, `truncated`, `observation too long`, etc.) and `view_file` pagination.
   - Verifies forbidden guessing/paraphrasing from truncated regions.
   - Verifies requirement that fenced diff/code blocks must be backed byte-for-byte by untruncated output or `view_file`.
4. `test_skill_anti_hallucination_and_topic_diff_directives(skill_content)`:
   - Verifies prohibition of ad-hoc terminal scripts (`python3 -c`, raw `git diff`) dumping hunks directly to stdout.
   - Verifies `temp_topic_diff.txt` command with pathspec `-- "<file>"` and `--find-renames --find-copies`.
   - Verifies root-commit empty tree variant for `temp_topic_diff.txt`.
   - Verifies requirement of prior `view_file` inspection (reading through EOF) before emitting fenced diff blocks.
5. `test_robustness_guide_truncation_and_grounded_quotation(robustness_guide_content)`:
   - Verifies dedicated section on truncation handling and grounded quotation invariants.
   - Verifies failure mode analysis (terminal truncation, generative hallucination).
   - Verifies `temp_topic_diff.txt` documentation in §1 (Tooling Contract), §3 (Roles), and §7 (Cleanup).
6. Ensure 100% pass rate across all existing tests in `test_explain_diff.py`.

## 4. Verification & Testing Strategy
- Run `python3 ~/.gemini/scripts/run_in_env.py <worktree_path> pytest skills/explain-diff/tests/test_explain_diff.py`
- Run lint checks via `python3 ~/.gemini/scripts/run_in_env.py <worktree_path> ruff check .`
- Static verification of symlink `GEMINI.md -> AGENTS.md` continuity.
