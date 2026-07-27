---
name: spec-driven-development
description: Define testable requirements and obtain explicit approval before planning or implementation.
---

# Spec-Driven Development

Write a specification before making any non-trivial codebase change. Use a short specification for small changes; do not skip the gate.

## Process

1. Inspect relevant requirements and existing behavior.
2. Surface ambiguities, assumptions, dependencies, and risks.
3. Define:
   - objective and user-visible outcome
   - in-scope and out-of-scope work
   - constraints and compatibility requirements
   - specific, measurable acceptance criteria
   - behavioral testing strategy or, for static-only changes, appropriate validation
4. Resolve contradictions instead of guessing.
5. Present the specification for explicit human approval.

## Approval Gate

Pause after drafting the specification. Do not create an implementation plan, edit repository files, or begin implementation until a human explicitly approves it. If requirements change later, update the specification and obtain renewed approval before continuing.

## Verification

- Objectives, scope, boundaries, and constraints are explicit.
- Acceptance criteria are observable and testable.
- Behavioral requirements are distinguished from static content or configuration requirements.
- Assumptions and unresolved decisions are visible.
- Explicit human approval is recorded before planning begins.
