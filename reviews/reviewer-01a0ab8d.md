# Review: reviewer-01a0ab8d
VERDICT: NEEDS_REVISION
AUDITED_SHA: 443e9f6d5c281c559d83d0b0f66ccef553b44a2b

## Audit Findings
- [ ] **[Severity: P1] [Section: Spec §3.1] Truncation Signal Set Incomplete & view_file Pagination Gap**
  - **Defect / Gap**: Spec defines circuit breaker only for `<truncated N lines>` / `<truncated N bytes>`. Real agent runtimes also emit variants like `observation too long`, `<output truncated>`, or system-level truncation. More critically, `view_file` itself paginates at 800 lines without `<truncated>` marker; an agent could view first chunk of `temp_topic_diff.txt` and then hallucinate remaining hunks, bypassing breaker. No requirement to read until EOF per robustness_guide §6. This leaves silent hallucination avenue for large topics (>800 lines).
  - **Actionable Fix**: Expand AGENTS.md breaker to: "If any tool output indicates truncation (`<truncated`, `truncated`, `observation too long`, or view_file pagination with more lines remaining), forbid reciting/paraphrasing/guessing from unviewed region." Mandate in SKILL.md §4b and robustness_guide: calculate total line count, iterate `view_file` until StartLine > total before quoting. Add test `test_truncation_circuit_breaker` to assert EOF-loop requirement.

- [ ] **[Severity: P1] [Section: Spec §3.2] Topic Diff Pathspec Quoting & Rename/Copy Source Loss**
  - **Defect / Gap**: Command template `git diff "<ref>...<hash>" --find-renames --find-copies -- <files...> > scratch/temp_topic_diff.txt` uses unquoted `<files...>` placeholder. Fails on paths with spaces, quotes, newlines, `$()`, and risks shell injection. Also, path-limited diff omits rename/copy source when source outside pathspec (Git only inspects target). Without fallback to global status records, agent will mislabel rename as addition and break U vs M reconciliation (`M >= U` invariant). Existing file-by-file flow (§6b) documents using `temp_diff_paths.txt` / `temp_diff_numstat.txt` for source tags; topic flow omits this.
  - **Actionable Fix**: Change template to `git diff "<ref>...<hash>" --find-renames --find-copies -- "<file1>" "<file2>" > scratch/temp_topic_diff.txt` (each file quoted) and add note: "If topic includes rename/copy target without source in pathspec, use global `temp_diff_paths.txt` / `temp_diff_numstat.txt` to emit `[rename: old -> new]` / `[copy: src -> dst]` metadata tags per robustness_guide §4." Keep `--find-renames --find-copies` flags. Update test to verify quoted per-file pattern and metadata fallback mention.

- [ ] **[Severity: P1] [Section: Spec §3.2 & §3.3] Missing Fail-Closed Verification for temp_topic_diff.txt**
  - **Defect / Gap**: Existing §1h requires exit status 0 verification for `temp_diff_stat.txt`, `temp_diff_numstat.txt`, `temp_diff_all.txt`, `temp_diff_paths.txt` with fail-closed stop. New artifact `temp_topic_diff.txt` is also a Git-generated diff that can fail (invalid pathspec, bad SHA, permission). Spec does not extend fail-closed check to it. Agent could read stale/empty file from previous topic and hallucinate diff, violating circuit breaker intent.
  - **Actionable Fix**: Extend fail-closed directive in SKILL.md §1h and robustness_guide to include `temp_topic_diff.txt`: "Verify exit status 0 for every topic diff generation; on non-zero, STOP, report Git error output, do not read partial file, do not reconcile, do not emit fenced diff." Add to test `test_fail_closed_artifact_exit_status_checks` verification list.

- [ ] **[Severity: P2] [Section: Spec §3.2] Vague 'Immediate Turn History' Window for Grounded Quotation**
  - **Defect / Gap**: "Emitting any fenced diff block without prior view_file inspection in the immediate turn history is strictly forbidden" – undefined window (1 turn? N turns? Since last write?). Allows quoting from stale view after file overwrite (topic2 quoting topic1 content) or view of unrelated file (e.g., `temp_diff_all.txt` instead of `temp_topic_diff.txt`). Breaks byte-for-byte grounding guarantee.
  - **Actionable Fix**: Define precisely per Ponytail: "After writing `temp_topic_diff.txt` for a topic, agent MUST inspect it via `view_file` (until EOF) in same topic iteration before any fenced diff emission. Quoted bytes MUST be covered by view_file output in this iteration; views from prior topics or other scratch files do not satisfy." Update SKILL.md §4b and robustness_guide section accordingly, and test for "same iteration" language.

- [ ] **[Severity: P2] [Section: Spec §3.2 & §3.3] Binary/Metadata Handling Gap in Topic Diff**
  - **Defect / Gap**: Spec mandates inspecting `temp_topic_diff.txt` via `view_file` before quoting verbatim in fenced diff blocks, but does not distinguish binary files (`-\\t-\\t<path>` in numstat) which must use metadata tags `[binary file: ...]`, `[binary deletion: ...]`, `[submodule: ...]`, `[symlink: ...]`, etc., per existing coverage invariant. Risk of attempting to render binary diff as text fenced block, causing corruption or hallucinated hunks.
  - **Actionable Fix**: Add to §4b and robustness_guide Truncation Handling section: "For entries where numstat reports `-\\t-\\t`, use metadata tags per §2 Binary/Deletion/Rename handling, not fenced diff blocks. Fenced diff blocks only for text hunks verified via view_file." Ensure cleanup section still lists `temp_topic_diff.txt`.

- [ ] **[Severity: Nit] [Section: Spec §3.1 & §3.4] AGENTS.md Global Scope & Test Minimalism**
  - **Defect / Gap**: Adding verbatim quotation breaker to global AGENTS.md affects all skills, not just explain-diff – intentional but should note backward compat: other skills already rely on view_file for large outputs, so no break. Test spec adds 3 new tests; ensure they use existing fixtures (`agents_content`, `skill_content`, `robustness_guide_content`) and do not duplicate existing assertions (YAGNI).
  - **Actionable Fix**: Keep AGENTS.md addition minimal: 2-3 lines defining breaker, no speculative hooks. In test file, reuse existing fixtures, assert only new directives, keep 100% pass rate requirement. Document that `GEMINI.md -> AGENTS.md` symlink continuity remains.

## Summary
Spec correctly identifies root cause (terminal truncation -> hallucinated CITATION.cff) and proposes mechanical extraction via path-limited scratch file. Core approach is sound and aligns with existing robustness patterns (scratch files, view_file, --find-renames --find-copies). However P1 gaps around truncation signal completeness + view_file pagination, pathspec quoting + rename source loss, and missing fail-closed for new artifact must be fixed to close all hallucination avenues. With those fixes, spec will be APPROVE-ready and preserve backward compatibility with existing test contracts.

## Backwards Compatibility Check
- Existing tests check for --stat, --numstat -z, --name-status -z, --find-renames --find-copies, NUL parsing, KaTeX $K \le 1$, topic count $1 \le T \le 6$, etc. Adding temp_topic_diff.txt does not conflict; no existing test asserts exclusive file list.
- Adding AGENTS.md breaker is additive, does not remove existing Empirical Grounding.
- No change to tri-lens tokens [t]/[c]/[f] or KaTeX notation – respects Non-Goals.

## YAGNI & Minimal Diff Assessment
- Additions are concise and directly address incident. No speculative abstractions.
- Command templates reuse existing flags (--find-renames --find-copies) – good.
- Could reduce duplication by referencing existing scratch dir creation and quoting rules rather than repeating full path, but acceptable for clarity.
