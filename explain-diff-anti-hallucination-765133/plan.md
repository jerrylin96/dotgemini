# Implementation Plan: explain-diff-anti-hallucination

## Overview
Implement anti-truncation circuit breaker and mechanical topic diff extraction across `AGENTS.md`, `skills/explain-diff/SKILL.md`, and `skills/explain-diff/resources/robustness_guide.md`, backed by test suite expansion in `skills/explain-diff/tests/test_explain_diff.py`.

## Execution Strategy
Standard sequential implementation under isolated git worktree:
`WORKTREE_PATH=/Users/jlin404/.gemini/tmp/worktrees/gemini_explain-diff-anti-hallucination-765133`

---

## Tasks

### Task 1: Test Suite Preparation & Regression Updates (RED Tests)
- **Target File**: `skills/explain-diff/tests/test_explain_diff.py`
- **RED Test Spec**:
  1. Update `test_root_commit_cross_reference_corrected` regex to `steps?\s+1c[–-]1f,\s*(?:4b,\s*)?6b` to support Step 4b without breaking existing test contract.
  2. Update `test_fail_closed_artifact_exit_status_checks` to assert `"temp_topic_diff.txt"` is included in the verified artifacts.
  3. Add `test_truncation_circuit_breaker_in_agents_md(agents_content)`:
     - Asserts `AGENTS.md` contains the truncation circuit breaker.
     - Asserts prohibition on guessing, reciting, or paraphrasing from truncated regions.
     - Asserts coverage of truncation indicators (`<truncated`, `observation too long`, `stdout_truncated: true`, or unviewed `view_file` pagination).
     - Asserts requirement that fenced diff/code blocks cited as empirical truth must be backed byte-for-byte by untruncated tool output or line-numbered `view_file`.
  4. Add `test_skill_anti_hallucination_and_topic_diff_directives(skill_content)`:
     - Asserts prohibition against ad-hoc terminal scripts (`python3 -c`, raw `git diff`) dumping diff hunks directly to stdout.
     - Asserts `temp_topic_diff.txt` command with pathspec `-- "<file>"` and `--find-renames --find-copies`.
     - Asserts root-commit empty-tree two-argument variant for `temp_topic_diff.txt`.
     - Asserts prior `view_file` inspection through EOF in active context before emitting fenced diff blocks.
  5. Add `test_robustness_guide_truncation_and_grounded_quotation(robustness_guide_content)`:
     - Asserts dedicated section "Truncation Handling & Grounded Quotation Invariants".
     - Asserts documentation of failure modes (terminal truncation leading to generative hallucination).
     - Asserts `temp_topic_diff.txt` presence in §1 Tooling Contract, §3 Roles, and §7 Cleanup.
- **GREEN Implementation Target**: These tests will initially fail against current `AGENTS.md`, `SKILL.md`, and `robustness_guide.md`, providing cryptographic proof of RED test rigor.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_explain-diff-anti-hallucination-765133 pytest skills/explain-diff/tests/test_explain_diff.py
  ```

### Task 2: Global Agent Guide Update (`AGENTS.md`)
- **Target File**: `AGENTS.md`
- **RED Test Spec**: `test_truncation_circuit_breaker_in_agents_md` (from Task 1).
- **GREEN Implementation Target**:
  In §3 *Core Operating Behaviors -> Empirical Grounding (Zero Hallucinated Claims)*:
  Add explicit Verbatim Quotation & Truncation Circuit Breaker:
  - Fenced `diff` or code blocks cited as empirical truth MUST be backed byte-for-byte by untruncated tool output or line-numbered `view_file` citations in context.
  - Truncation Circuit Breaker: If any tool output indicates truncation (`<truncated N lines>`, `<truncated N bytes>`, `... output truncated ...`, `observation too long`, `stdout_truncated: true`, or unviewed `view_file` pagination where lines remain in the artifact), the agent is strictly forbidden from reciting, paraphrasing, or guessing any content from the truncated or unviewed region. It MUST call `view_file` on the source artifact through EOF or write targeted output to a scratch file and view it.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_explain-diff-anti-hallucination-765133 pytest skills/explain-diff/tests/test_explain_diff.py -k test_truncation_circuit_breaker
  ```

### Task 3: Skill Specification Update (`skills/explain-diff/SKILL.md`)
- **Target File**: `skills/explain-diff/SKILL.md`
- **RED Test Spec**: `test_skill_anti_hallucination_and_topic_diff_directives`, `test_root_commit_cross_reference_corrected`, `test_fail_closed_artifact_exit_status_checks` (from Task 1).
- **GREEN Implementation Target**:
  1. In §1 (*Get the Diff Safely & Extract Commits*): Add prohibition against running ad-hoc terminal scripts (`python3 -c`, raw `git diff`, etc.) dumping diff hunks directly to stdout; mandate scratch file redirection. Add `temp_topic_diff.txt` to managed scratch files.
  2. In §1h (*Fail-Closed Artifact & Exit Status Verification*): Add `temp_topic_diff.txt` to exit status 0 verification list.
  3. In Context Resolution (Commit mode): Update root-commit reference to `(steps 1c–1f, 4b, 6b)`.
  4. In §4 (*Topic-by-Topic Walkthrough Flow (`[t]`)*):
     - Mandate topic diff extraction before presenting topic hunks:
       - Normal: `git diff "<reference_commit_hash>...<commit_hash>" --find-renames --find-copies -- "<file1>" "<file2>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_topic_diff.txt"`
       - Root commit: `git diff "<reference_commit_hash>" "<commit_hash>" --find-renames --find-copies -- "<file1>" "<file2>" > "<appDataDir>/brain/<conversation-id>/scratch/temp_topic_diff.txt"`
     - Add pathspec individual quoting and rename/copy source handling directives.
     - Mandate exit status 0 verification and `view_file` inspection through EOF in active context before emitting fenced diff blocks.
     - Mandate metadata tags (per §2) for `-\t-\t` binary/metadata entries.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_explain-diff-anti-hallucination-765133 pytest skills/explain-diff/tests/test_explain_diff.py -k "test_skill or test_root or test_fail_closed"
  ```

### Task 4: Robustness Guide Update (`skills/explain-diff/resources/robustness_guide.md`)
- **Target File**: `skills/explain-diff/resources/robustness_guide.md`
- **RED Test Spec**: `test_robustness_guide_truncation_and_grounded_quotation` (from Task 1).
- **GREEN Implementation Target**:
  1. In §1 (*Tooling Contract*): Add `temp_topic_diff.txt` to primary human-readable text artifacts for `view_file`.
  2. In §3 (*Temporary File Roles*): Add `temp_topic_diff.txt` description.
  3. Add dedicated section **8. Truncation Handling & Grounded Quotation Invariants**:
     - Detail stdout truncation failure mode and LLM generative hallucination mechanism.
     - Detail mechanical path-scoped scratch diff extraction protocol (`temp_topic_diff.txt`).
     - Detail `view_file` EOF pagination and fail-closed requirements.
     - Detail binary and non-text metadata tag handling.
  4. In §7 (*Cleanup*): Include `temp_topic_diff.txt` in allowed scratch file deletions.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_explain-diff-anti-hallucination-765133 pytest skills/explain-diff/tests/test_explain_diff.py -k test_robustness_guide
  ```

### Task 5: End-to-End Regression & Linter Verification
- **Target Files**: All modified files.
- **GREEN Target**: 100% test pass rate across all 27+ tests in `test_explain_diff.py`. Ruff check clean. Symlink `GEMINI.md -> AGENTS.md` intact.
- **Verify Commands**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_explain-diff-anti-hallucination-765133 pytest skills/explain-diff/tests/test_explain_diff.py
  python3 ~/.gemini/scripts/run_in_env.py /Users/jlin404/.gemini/tmp/worktrees/gemini_explain-diff-anti-hallucination-765133 ruff check .
  ```
