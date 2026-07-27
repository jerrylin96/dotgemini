---
name: debugging-and-error-recovery
description: Stop on unexpected failures, preserve evidence, and fix verified root causes systematically.
---

# Debugging and Error Recovery

When behavior, tests, builds, or validation fail unexpectedly, stop adding changes. Errors compound when implementation continues on a broken base.

## Stop-the-Line Process

1. **Preserve:** capture exact errors, logs, inputs, environment details, and reproduction steps.
2. **Reproduce:** make the failure occur reliably. If intermittent, record frequency and controlled variables.
3. **Localize:** narrow the failing boundary, component, and last known good state.
4. **Reduce:** remove unrelated inputs and code until the smallest failing case remains.
5. **Hypothesize:** state one falsifiable root-cause theory at a time and test it.
6. **Fix:** change the shared source of the failure, not a downstream symptom.
7. **Guard:** for behavioral bugs, add a regression test that fails before the fix and passes after it. For static-only defects, add or run the appropriate static validation instead.
8. **Verify:** run focused checks first, then relevant broader regressions.
9. **Resume:** continue planned implementation only after verification succeeds.

## Diagnostic Discipline

- Read the complete error before editing.
- Change one variable at a time.
- Trace callers and data flow across the failing boundary.
- Compare with a known-good path or revision when available.
- Treat test defects, environment defects, and product defects as separate hypotheses.
- Revert speculative diagnostics that do not contribute to the final fix.

## Recovery Gate

Do not bypass, weaken, or delete a valid check merely to obtain a pass. If the failure cannot be resolved, report the preserved evidence, attempted hypotheses, current impact, and remaining uncertainty rather than claiming recovery.
