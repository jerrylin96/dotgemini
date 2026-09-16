# Adversarial Review Prompt: RED Test Suite (explain-diff-anti-hallucination)

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
- **Milestone**: Phase 2 (RED Test Suite - Failing)
- **Target File**: `skills/explain-diff/tests/test_explain_diff.py`

### Task Description
Perform an adversarial audit of the RED test suite in `skills/explain-diff/tests/test_explain_diff.py`.
Verify:
1. **Cryptographic Proof of Failure**: Do the new/updated tests cleanly fail on the un-implemented codebase (22 passed, 5 failed)?
2. **Assertion Tightness**: Are assertions rigorous enough to prevent false positives (no overly broad regexes, permissive fallbacks, or un-bounded section splits)?
3. **Spec Parity**: Do the test assertions strictly enforce all invariants specified in `spec.md` (Revision 1)?

### Delivery Modes
- **Mode A (Dedicated Branch)**: Branch `review/explain-diff-anti-hallucination-765133/<REVIEWER_ID>`, commit findings to `review.md`, and push.
- **Mode B (Shared Sandbox Branch)**: Create/update ONLY `reviews/<REVIEWER_ID>.md` on the shared branch, stage ONLY that file (`git add reviews/<REVIEWER_ID>.md`), and push via `git pull --rebase origin <branch>`.

### Output Format Schema
```markdown
# Review: <REVIEWER_ID>
VERDICT: [APPROVE | NEEDS_REVISION | REJECT]
AUDITED_SHA: <sha>

## Audit Findings
- [ ] **[Severity: P0|P1|P2|Nit] [Section: Test Name] Title**
  - **Defect / Gap**: Concrete failure mode or counterexample.
  - **Actionable Fix**: Minimal concrete fix complying with Ponytail.
```
