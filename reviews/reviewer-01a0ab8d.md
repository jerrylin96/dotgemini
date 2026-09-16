# Review: reviewer-01a0ab8d
VERDICT: NEEDS_REVISION
AUDITED_SHA: 443e9f6d5c281c559d83d0b0f66ccef553b44a2b

## Audit Findings
- [ ] **[Severity: P1] [Section: Spec §3.1] Truncation Signal Set Incomplete & view_file Pagination Gap**
  - **Defect / Gap**: Spec defines circuit breaker only for `<truncated N lines>` / `<truncated N bytes>`. Real agent runtimes also emit variants like `... output truncated ...`, `observation too long`, `<output truncated>`, or tool metadata fields like `stdout_truncated: true`. More critically, `view_file` itself paginates at 800 lines without `<truncated>` markers; an agent could view the first chunk of `temp_topic_diff.txt` and then hallucinate remaining hunks, bypassing the circuit breaker. No requirement is established to read iteratively until EOF per robustness_guide §6. This leaves a silent hallucination avenue for large topics (>800 lines).
  - **Actionable Fix**: Expand AGENTS.md breaker to: "If any tool output indicates truncation (`<truncated`, `truncated`, `observation too long`, `stdout_truncated: true`, or view_file pagination with more lines remaining), forbid reciting/paraphrasing/guessing from unviewed region." Mandate in SKILL.md §4b and robustness_guide: calculate total line count, iterate `view_file` until StartLine > total before quoting.

- [ ] **[Severity: P1] [Section: Spec §3.2 & §3.3] Topic Diff Pathspec Quoting & Rename/Copy Source Loss**
  - **Defect / Gap**: Command template `git diff "<ref>...<hash>" --find-renames --find-copies -- <files...> > scratch/temp_topic_diff.txt` uses an unquoted `<files...>` placeholder. This fails on paths with spaces, quotes, newlines, and risks shell injection. Furthermore, Git pathspec filtering (`-- <files...>`) suppresses rename detection unless both the source path (`<old_path>`) and target path (`<new_path>`) are passed to the pathspec. If a topic contains a renamed file and only `<new_path>` is passed, Git outputs a false `new file mode 100644` diff showing 100% added lines, which directly contradicts the `[rename: old -> new]` metadata tag mandated in Step 4b. Existing file-by-file flow (§6b) documents using `temp_diff_paths.txt` / `temp_diff_numstat.txt` for source tags; topic flow omits this.
  - **Actionable Fix**: Change template to `git diff "<ref>...<hash>" --find-renames --find-copies -- "<file1>" "<file2>" > scratch/temp_topic_diff.txt` (each file individually quoted) and add note: "If topic includes rename/copy target without source in pathspec, include both source and target paths in pathspec or use global `temp_diff_paths.txt` / `temp_diff_numstat.txt` to emit `[rename: old -> new]` / `[copy: src -> dst]` metadata tags per robustness_guide §4." Keep `--find-renames --find-copies` flags.

- [ ] **[Severity: P1] [Section: Spec §3.2 & §3.4] Root-Commit Command Addition Breaks Existing Test Contract**
  - **Defect / Gap**: Spec §3.2 introduces a two-argument root-commit empty-tree diff command in Step 4b (`git diff "<reference_commit_hash>" "<commit_hash>" --find-renames --find-copies -- <files...> > .../temp_topic_diff.txt`). In `skills/explain-diff/SKILL.md` (Context Resolution -> Commit mode), existing documentation states that two-argument diffs are used for `(steps 1c–1f, 6b)`. Existing test `test_root_commit_cross_reference_corrected` in `skills/explain-diff/tests/test_explain_diff.py` explicitly enforces this via `assert re.search(r"steps?\s+1c[–-]1f,\s*6b", skill_content)`. If `SKILL.md` is updated to include Step 4b (`steps 1c–1f, 4b, 6b`), the test suite will immediately fail. Conversely, leaving `SKILL.md` unchanged introduces an internal documentation inconsistency. Spec §3.4 lists "Ensure 100% pass rate across all existing tests in test_explain_diff.py" without specifying the necessary test adjustment.
  - **Actionable Fix**: In Spec §3.4, specify updating `test_root_commit_cross_reference_corrected` to accept `4b` (e.g. `r"steps?\s+1c[–-]1f,\s*(?:4b,\s*)?6b"`), and in Spec §3.2 mandate updating the cross-reference in `SKILL.md` to `(steps 1c–1f, 4b, 6b)`.

- [ ] **[Severity: P1] [Section: Spec §3.2 & §3.3] Missing Fail-Closed Verification for temp_topic_diff.txt**
  - **Defect / Gap**: Existing §1h requires exit status 0 verification for `temp_diff_stat.txt`, `temp_diff_numstat.txt`, `temp_diff_all.txt`, `temp_diff_paths.txt` with fail-closed stop. New artifact `temp_topic_diff.txt` is also a Git-generated diff that can fail (invalid pathspec, bad SHA, permissions error). Spec does not extend fail-closed check to it. If the command fails, shell redirection truncates the file to 0 bytes or leaves a previous topic's content intact, causing the agent to read stale/empty files and hallucinate hunks.
  - **Actionable Fix**: Extend fail-closed directive in SKILL.md §1h and robustness_guide to include `temp_topic_diff.txt`: "Verify exit status 0 for every topic diff generation; on non-zero, STOP, report Git error output, do not read partial file, do not reconcile, do not emit fenced diff." Add to test `test_fail_closed_artifact_exit_status_checks` verification list.

- [ ] **[Severity: P2] [Section: Spec §3.2] Vague 'Immediate Turn History' Window for Grounded Quotation**
  - **Defect / Gap**: "Emitting any fenced diff block without prior view_file inspection in the immediate turn history is strictly forbidden" – undefined window (1 turn? N turns? Since last write?). Allows quoting from stale view after file overwrite (topic2 quoting topic1 content) or view of unrelated file (e.g., `temp_diff_all.txt` instead of `temp_topic_diff.txt`). In multi-turn Q&A (§7), it could force redundant re-reads of recently viewed hunks if interpreted as strictly the current turn.
  - **Actionable Fix**: Define precisely per Ponytail: "After writing `temp_topic_diff.txt` for a topic, agent MUST inspect it via `view_file` (until EOF) in same topic iteration before any fenced diff emission. Quoted bytes MUST be covered by view_file output in context; views from prior topics or other scratch files do not satisfy. For multi-turn Q&A, hunks must be present in active context from prior untruncated view_file calls; if evicted, re-read via view_file before quoting."

- [ ] **[Severity: P2] [Section: Spec §3.2 & §3.3] Binary/Metadata Handling Gap in Topic Diff**
  - **Defect / Gap**: Spec mandates inspecting `temp_topic_diff.txt` via `view_file` before quoting verbatim in fenced diff blocks, but does not distinguish binary files (`-\t-\t<path>` in numstat) which must use metadata tags `[binary file: ...]`, `[binary deletion: ...]`, `[submodule: ...]`, `[symlink: ...]`, etc., per existing coverage invariant. Risk of attempting to render binary diff as text fenced block, causing corruption or hallucinated hunks.
  - **Actionable Fix**: Add to §4b and robustness_guide Truncation Handling section: "For entries where numstat reports `-\t-\t`, use metadata tags per §2 Binary/Deletion/Rename handling, not fenced diff blocks. Fenced diff blocks only for text hunks verified via view_file." Ensure cleanup section still lists `temp_topic_diff.txt`.

- [ ] **[Severity: P2] [Section: Spec §3.2] Single-File Hunk Loophole in Terminal Script Prohibition**
  - **Defect / Gap**: Spec §3.2 forbids terminal scripts that dump "bulk multi-file hunks directly to stdout where terminal truncation occurs." Restricting the prohibition to "bulk multi-file hunks" creates a loophole: an agent inspecting a single large file could dump hunks directly to stdout via `python3 -c` or `git diff`, triggering terminal truncation and hallucination on single files.
  - **Actionable Fix**: Remove the "bulk multi-file" qualifier in Spec §3.2. Mandate that ANY git diff hunks (single-file or multi-file) must be redirected to scratch files and inspected via `view_file`.

- [ ] **[Severity: Nit] [Section: Spec §3.3] Omission of `temp_topic_diff.txt` from `robustness_guide.md` §1 Tooling Contract**
  - **Defect / Gap**: Spec §3.3 details updates for `robustness_guide.md` §3 (Roles) and §7 (Cleanup), but omits §1 (Tooling Contract). `robustness_guide.md` §1 enumerates human-readable text artifacts intended for `view_file`. Omitting `temp_topic_diff.txt` leaves the primary viewer contract incomplete.
  - **Actionable Fix**: Add `temp_topic_diff.txt` to the enumerated list of primary viewer text artifacts in `robustness_guide.md` §1.

- [ ] **[Severity: Nit] [Section: Spec §3.1 & §3.4] AGENTS.md Global Scope & Test Minimalism**
  - **Defect / Gap**: Adding verbatim quotation breaker to global AGENTS.md affects all skills, not just explain-diff – intentional but should note backward compat: other skills already rely on view_file for large outputs, so no break. Test spec adds 3 new tests; ensure they use existing fixtures (`agents_content`, `skill_content`, `robustness_guide_content`) and do not duplicate existing assertions (YAGNI).
  - **Actionable Fix**: Keep AGENTS.md addition minimal: 2-3 lines defining breaker, no speculative hooks. In test file, reuse existing fixtures, assert only new directives, keep 100% pass rate requirement. Document that `GEMINI.md -> AGENTS.md` symlink continuity remains.

## Summary
Spec correctly identifies root cause (terminal truncation -> hallucinated CITATION.cff) and proposes mechanical extraction via path-limited scratch file. Core approach is sound and aligns with existing robustness patterns (scratch files, view_file, --find-renames --find-copies). However, P1 gaps around truncation signal completeness + view_file pagination, pathspec quoting + rename source loss, root-commit cross-reference regex breakage, and missing fail-closed verification for the new artifact must be resolved to close all hallucination avenues and maintain test suite integrity.

## Backwards Compatibility Check
- Existing tests check for --stat, --numstat -z, --name-status -z, --find-renames --find-copies, NUL parsing, KaTeX $K \le 1$, topic count $1 \le T \le 6$, etc. Adding temp_topic_diff.txt does not conflict; no existing test asserts exclusive file list.
- Existing test `test_root_commit_cross_reference_corrected` specifically checks for regex `steps?\s+1c[–-]1f,\s*6b`. Introducing Step 4b root-commit commands requires relaxing this test regex to avoid regression failure.
- Adding AGENTS.md breaker is additive, does not remove existing Empirical Grounding.
- No change to tri-lens tokens [t]/[c]/[f] or KaTeX notation – respects Non-Goals.

## YAGNI & Minimal Diff Assessment
- Additions are concise and directly address the truncation incident. No speculative abstractions.
- Command templates reuse existing flags (--find-renames --find-copies) – good.
- Minimizes diff footprint by keeping changes scoped strictly to AGENTS.md, explain-diff SKILL.md, and robustness_guide.md.
