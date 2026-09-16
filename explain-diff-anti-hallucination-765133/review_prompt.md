# Adversarial Review Prompt: Feature Spec (explain-diff-anti-hallucination)

### 🪪 Reviewer Identification Proof (Mandatory Top Banner)
External reviewers MUST output this exact header at the top of their chat text (before any other text):
```text
### 🪪 Reviewer Identification Proof
- Reviewer ID: reviewer-<id>
- Target SHA Audited: <commit-sha>
- Review File: reviews/reviewer-<id>.md
- Push Commit SHA: <push-sha>
```
*Note: If you already established your `REVIEWER_ID` in an earlier turn, YOU MUST REUSE IT. Do NOT generate a new ID.*

---

### Review Context
- **Target Branch**: `gemini/explain-diff-anti-hallucination-765133`
- **Milestone**: Phase 1a (Feature Specification)
- **Target File**: `explain-diff-anti-hallucination-765133/spec.md`

### Task Description
Perform an adversarial audit of `explain-diff-anti-hallucination-765133/spec.md`.
Focus on:
1. **Truncation Circuit Breaker Rigor**: Does the specification effectively close all avenues for LLM hallucination when tool stdout is truncated?
2. **Topic Diff Extraction Feasibility**: Does the `temp_topic_diff.txt` command handle pathspecs, renames, copies, and root commits properly?
3. **Backwards Compatibility**: Do any changes break existing test contracts or workflows?
4. **YAGNI & Minimal Diff**: Are the proposed additions concise, clear, and free of speculative abstractions?

### Delivery Modes
- **Mode A (Dedicated Branch)**: Branch `review/explain-diff-anti-hallucination-765133/<REVIEWER_ID>`, commit findings to `review.md`, and push.
- **Mode B (Shared Sandbox Branch)**: Create/update ONLY `reviews/<REVIEWER_ID>.md` on the shared branch, stage ONLY that file (`git add reviews/<REVIEWER_ID>.md`), and push via `git pull --rebase origin <branch>`.

### Output Format Schema
```markdown
# Review: <REVIEWER_ID>
VERDICT: [APPROVE | NEEDS_REVISION | REJECT]
AUDITED_SHA: <sha>

## Audit Findings
- [ ] **[Severity: P0|P1|P2|Nit] [Section: Spec §X] Title**
  - **Defect / Gap**: Concrete failure mode or counterexample.
  - **Actionable Fix**: Minimal concrete fix complying with Ponytail.
```
