---
name: incremental-implementation
description: Implement an approved plan in minimal verified slices that keep the system working.
---

# Incremental Implementation

Implement one approved slice at a time in an isolated feature branch. Prefer the smallest complete path through the system over broad horizontal layers.

## Slice Cycle

For each slice:

1. Confirm its acceptance criteria and affected code path.
2. Apply the reuse-first, minimum-code discipline from `ponytail`.
3. For behavioral changes, follow RED-GREEN-REFACTOR:
   - observe the focused test fail for the expected reason
   - write the minimum implementation that makes it pass
   - simplify while keeping tests green
4. For static-only changes, make the minimum edit and run the planned static validation; do not label this TDD.
5. Run focused verification, then the relevant broader regression checks.
6. Inspect the diff for accidental scope growth.
7. Record an atomic checkpoint before starting the next slice when repository workflow requires it.

## Slicing Strategies

- **Vertical:** complete one user-visible path across necessary layers.
- **Contract-first:** establish a shared contract, implement each side against it, then verify integration.
- **Risk-first:** prove the most uncertain dependency or behavior before lower-risk work.

## Stop-the-Line Gate

If a test, build, or validation unexpectedly fails, stop implementation. Preserve evidence and use systematic debugging. Do not continue to later slices until the root cause is fixed and relevant verification passes.

## Completion Gate

Implementation is complete only when every approved task has empirical verification, the full relevant regression suite passes, and the final diff remains within approved scope. Do not claim success from code inspection alone.
