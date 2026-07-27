---
name: planning-and-task-breakdown
description: Convert an approved specification into small ordered tasks with explicit verification.
---

# Planning and Task Breakdown

Plan only after the specification has explicit human approval. Planning is read-only: inspect relevant code and conventions, but do not implement changes.

## Process

1. Trace existing code paths, callers, tests, and project conventions.
2. Identify dependencies, risks, unknowns, and opportunities to reuse existing code.
3. Split work into small, ordered slices, preferably touching no more than about five files each.
4. Give every task a concrete outcome, affected area, and exact verification method.
5. Mark dependencies and checkpoints between major phases.

## Verification Design

Classify each task before assigning verification:

- **Behavioral change:** specify the test that must fail for the intended reason before implementation, the minimum implementation target, and the command that proves the behavior passes afterward.
- **Static-only change:** specify the relevant parser, schema check, linter, build, or focused manual inspection. Do not invent a failing behavioral test when no runtime behavior changes.

Include broader regression verification where the change can affect existing behavior.

## Approval Gate

Present the complete plan for explicit human approval. Do not create an implementation branch, edit code, or begin a task until approval is received. If scope changes materially, revise the plan and request approval again.

## Verification

- Plan covers the full approved specification and nothing speculative.
- Tasks are small, ordered, and independently verifiable.
- Behavioral tasks contain RED, GREEN, and regression evidence requirements.
- Static-only tasks use appropriate static validation.
- Dependencies and exact verification commands are documented.
- Explicit human approval is recorded before implementation begins.
