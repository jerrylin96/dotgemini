---
name: code-review-and-quality
description: "Multi-axis code review across correctness, readability, architecture, security, and performance. Maps to /review. Use before merging any change."
---

## Overview
Every change gets reviewed before merge — no exceptions. Review covers five axes: correctness, readability, architecture, security, and performance. Approve when it definitely improves overall code health, even if it isn't perfect.

## When to Use
- Before merging any `gemini/*` branch
- After completing a feature implementation
- When evaluating code produced by another agent
- When refactoring existing code
- After any bug fix

> [!TIP]
> For adversarial / deep-dive merge reviews, see the [adversarial-review](../adversarial-review/SKILL.md) skill.

## The Five-Axis Review

### 1. Correctness
- Does code do what it claims?
- Matches spec/task requirements?
- Edge cases and error paths handled?
- Tests pass and test the right things?
- Off-by-one, race conditions, state inconsistencies?

### 2. Readability & Simplicity
- Understandable without author explaining?
- Descriptive names, consistent with project?
- Straightforward control flow, logically organized?
- Abstractions earning their complexity?
- Dead code artifacts?

### 3. Architecture
- Adheres to existing design patterns?
- Tight coupling where loose preferred?
- Leaking implementation details?
- Circular dependencies?
- Directory structure consistent?

### 4. Security
- Inputs validated, data sanitized?
- Secrets hardcoded? (never)
- Safe defaults for auth?
- Dependencies audited?

### 5. Performance
- O(n²) in tight loops?
- Unnecessary computation/fetching?
- Memory leaks, blocking main thread?
- Efficient data structures?

## Process
1. **Scope**: Review changed lines + context. If >100 lines, request split into smaller commits.
2. **Verify**: Run linters and tests via `run_in_env.py` as part of the review — don't trust "it works" claims without evidence.
3. **Label findings**: `[CRITICAL]`, `[IMPORTANT]`, `[SUGGESTION]`, `[FYI]`
4. **Synthesize**: Clear verdict — Approve or Request Changes.
5. **Re-review**: After fixes, verify again before merge.

## Common Rationalizations
| Rationalization | Reality |
|---|---|
| "It works, that's good enough" | Working but unreadable/insecure code creates compounding debt |
| "I wrote it, so I know it's correct" | Authors are blind to own assumptions |
| "We'll clean it up later" | Later never comes. Review is the quality gate. |
| "AI-generated code is probably fine" | AI code needs more scrutiny, not less |

## Red Flags
- Changes merged to main without review
- Review only checks if tests pass
- "LGTM" without evidence of actual review
- Large branches "too big to review" — split them
- No regression tests accompanying a bug fix

## Verification
- [ ] Tests pass (run via `run_in_env.py`)
- [ ] Build succeeds
- [ ] Manual verification done (if applicable)
- [ ] Verdict: Approve or Request Changes
