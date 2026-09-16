# Adversarial Review Prompt: Feature Plan (explain-diff-anti-hallucination)

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
- **Milestone**: Phase 1b (Implementation Plan)
- **Target File**: `explain-diff-anti-hallucination-765133/plan.md`

### Task Description
Perform an adversarial audit of `explain-diff-anti-hallucination-765133/plan.md`.
Focus on:
1. **TDD Rigor**: Does Task 1 write failing RED tests proving the failure of missing directives before implementing GREEN code?
2. **Task Atomicity & Dependencies**: Are the tasks cleanly ordered without circular dependencies?
3. **Parity with Approved Spec**: Does the plan implement all requirements and edge case fixes agreed upon in `spec.md` (Revision 1)?
4. **Worktree & Env Safety**: Are all commands targeted to the isolated worktree using `run_in_env.py`?
5. **YAGNI**: Is the plan free of bloated or unnecessary scaffolding?

### Delivery Modes
- **Mode A (Dedicated Branch)**: Branch `review/explain-diff-anti-hallucination-765133/<REVIEWER_ID>`, commit findings to `review.md`, and push.
- **Mode B (Shared Sandbox Branch)**: Create/update ONLY `reviews/<REVIEWER_ID>.md` on the shared branch, stage ONLY that file (`git add reviews/<REVIEWER_ID>.md`), and push via `git pull --rebase origin <branch>`.

### Output Format Schema
```markdown
# Review: <REVIEWER_ID>
VERDICT: [APPROVE | NEEDS_REVISION | REJECT]
AUDITED_SHA: <sha>

## Audit Findings
- [ ] **[Severity: P0|P1|P2|Nit] [Section: Plan Task Y] Title**
  - **Defect / Gap**: Concrete failure mode or counterexample.
  - **Actionable Fix**: Minimal concrete fix complying with Ponytail.
```
