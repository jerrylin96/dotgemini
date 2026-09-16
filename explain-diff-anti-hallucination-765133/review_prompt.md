# Adversarial Review Prompt: Feature Spec (explain-diff-anti-hallucination) - Revision 1

### 🪪 Reviewer Identification Proof (Mandatory Top Banner)
External reviewers MUST output this exact header at the top of their chat text (before any other text):
```text
### 🪪 Reviewer Identification Proof
- Reviewer ID: reviewer-<id>
- Target SHA Audited: <commit-sha>
- Review File: reviews/reviewer-<id>.md
- Push Commit SHA: <push-sha>
```
*Note: If you already established your `REVIEWER_ID` in an earlier turn (e.g. `reviewer-01a0ab8d`), YOU MUST REUSE IT. Do NOT generate a new ID.*

---

### Review Context
- **Target Branch**: `gemini/explain-diff-anti-hallucination-765133`
- **Milestone**: Phase 1a (Feature Specification - Revision 1)
- **Target File**: `explain-diff-anti-hallucination-765133/spec.md`

### Task Description
Perform an adversarial audit of the updated `explain-diff-anti-hallucination-765133/spec.md`.
Specific updates made based on `reviewer-01a0ab8d` feedback:
1. Expanded truncation signal set (`<truncated`, `observation too long`, `stdout_truncated: true`, unviewed pagination).
2. Mandated individual path quoting (`"<file1>" "<file2>"`) and rename/copy source handling.
3. Updated `test_root_commit_cross_reference_corrected` test contract to accommodate Step 4b.
4. Added fail-closed exit code 0 verification for `temp_topic_diff.txt`.
5. Defined active topic iteration inspection window and EOF pagination requirement.
6. Specified binary metadata handling (`-\t-\t` -> metadata tags, no text fenced diffs).
7. Removed "bulk multi-file" qualifier to forbid terminal dumping on ANY diff hunks.
8. Added `temp_topic_diff.txt` to `robustness_guide.md` §1 Tooling Contract.

Please verify whether all findings are resolved and update your review verdict.

### Delivery Modes
- **Mode A (Dedicated Branch)**: Branch `review/explain-diff-anti-hallucination-765133/<REVIEWER_ID>`, commit findings to `review.md`, and push.
- **Mode B (Shared Sandbox Branch)**: Create/update ONLY `reviews/<REVIEWER_ID>.md` on the shared branch, stage ONLY that file (`git add reviews/<REVIEWER_ID>.md`), and push via `git pull --rebase origin <branch>`.

### Output Format Schema
```markdown
# Review: <REVIEWER_ID>
VERDICT: [APPROVE | NEEDS_REVISION | REJECT]
AUDITED_SHA: <sha>

## Audit Findings
- [x] **[Severity: P1] [Section: Spec §3.1] Truncation Signal Set Incomplete & view_file Pagination Gap**
  - *(Resolved in commit <sha>)*
- [ ] **[Severity: ...] Title**
  - **Defect / Gap**: Concrete failure mode or counterexample.
  - **Actionable Fix**: Minimal concrete fix complying with Ponytail.
```
