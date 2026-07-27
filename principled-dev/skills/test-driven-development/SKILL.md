---
name: test-driven-development
description: Prove behavioral changes with observed RED-GREEN-REFACTOR cycles and regression checks.
---

# Test-Driven Development

Use TDD for new behavior, behavior changes, and bug fixes. A test that was never observed failing for the intended reason does not prove the change.

## RED-GREEN-REFACTOR

### RED

Write the smallest test that expresses one required behavior. Run it before changing production code and confirm it fails because the behavior is missing or incorrect, not because the test is broken.

### GREEN

Write only enough production code to satisfy the failing test. Run the focused test and confirm it passes.

### REFACTOR

Improve names, structure, and duplication without changing behavior. Re-run focused tests after each meaningful refactor, then run relevant broader regression tests.

## Bug-Fix Proof

1. Reproduce the reported bug.
2. Add a regression test that fails on the bug.
3. Confirm the failure matches the report.
4. Fix the shared root cause rather than one symptom.
5. Confirm the regression test passes.
6. Run the relevant wider suite.

## Behavioral TDD vs. Static Validation

TDD applies when executable behavior changes. Documentation, metadata, formatting, declarative configuration, and other static-only edits may have nothing meaningful to exercise through RED-GREEN-REFACTOR. Validate those changes with the strongest applicable parser, schema check, linter, build, or focused inspection instead.

Do not fabricate a behavioral test merely to claim TDD. If a configuration change affects runtime behavior, test that behavior; if it only changes static structure, report static validation accurately.

## Evidence Gate

Record the RED failure, GREEN pass, and relevant regression result. Never claim a test passed without current execution evidence. If required verification cannot run, state what remains unverified.
