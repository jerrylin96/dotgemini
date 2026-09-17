# Adversarial Review Prompt: GREEN Code Implementation (explain-diff-anti-hallucination)

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
- **Milestone**: Phase 3 (GREEN Code Implementation)
- **Target Diffs**:
  - `AGENTS.md` (§3 Core Operating Behaviors -> Empirical Grounding)
  - `skills/explain-diff/SKILL.md` (Context Resolution, §1, §4)
  - `skills/explain-diff/resources/robustness_guide.md` (§1, §3, §7, §8)
  - `skills/explain-diff/tests/test_explain_diff.py` (27 passed tests)

### Task Description
Perform an adversarial code review of the GREEN implementation.
Audit for:
1. **Circuit Breaker Coverage**: Does the addition in `AGENTS.md` comprehensively enforce the verbatim quotation & truncation circuit breaker across all agent workflows?
2. **Mechanical Topic Diff Robustness**: Does `SKILL.md` properly mandate individual path quoting (`"<file1>" "<file2>"`), rename/copy source handling, fail-closed verification, and EOF `view_file` reading before quoting?
3. **Robustness Guide Parity**: Does `robustness_guide.md` accurately capture the tooling contract, temporary file roles, allowed cleanup, and section 8 invariants?
4. **Code Quality & Ponytail**: Is the diff minimal, precise, free of speculative abstractions, and backward-compatible with all existing tests?

### Delivery Modes
- **Mode A (Dedicated Branch)**: Branch `review/explain-diff-anti-hallucination-765133/<REVIEWER_ID>`, commit findings to `review.md`, and push.
- **Mode B (Shared Sandbox Branch)**: Create/update ONLY `reviews/<REVIEWER_ID>.md` on the shared branch, stage ONLY that file (`git add reviews/<REVIEWER_ID>.md`), and push via `git pull --rebase origin <branch>`.

### Output Format Schema
```markdown
# Review: <REVIEWER_ID>
VERDICT: [APPROVE | NEEDS_REVISION | REJECT]
AUDITED_SHA: <sha>

## Audit Findings
- [ ] **[Severity: P0|P1|P2|Nit] [Section: File & Line] Title**
  - **Defect / Gap**: Concrete failure mode or counterexample.
  - **Actionable Fix**: Minimal concrete fix complying with Ponytail.
```
