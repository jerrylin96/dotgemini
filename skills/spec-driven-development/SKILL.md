---
name: spec-driven-development
description: Creates specs before coding. Maps to `/spec`. Use when starting a new project, feature, or significant change and no specification exists yet.
---

## Overview

Write the spec before the code. For trivial/small changes, the [lifecycle guide](../make-feature/resources/lifecycle-guide.md) permits skipping this gate — but for medium and large changes, a spec is required.

## When to Use

- Starting a new project or feature
- Significant refactoring or architectural changes
- Requirements are unclear or undocumented

## Process

### 1. Clarify Requirements

Define what to build. Identify ambiguities, missing requirements, assumptions.

> [!TIP]
> **(Antigravity Only)** If underspecified, use `/grill-me` to run an iterative interview until you hit ~95% confidence. In other runtimes, ask clarifying questions directly.

### 2. Draft the Spec

Cover: **Objectives**, **Scope**, **Project Structure**, **Code Style**, **Testing Strategy**, **Boundaries** (non-goals, constraints).

> [!TIP]
> **(Antigravity Only)** Store the spec as an artifact with `RequestFeedback: true` so the human gets a review prompt, or persist in an Obsidian vault per `AGENTS.md §9`. In other runtimes, write a `SPEC.md` in the repo and ask for explicit approval.

### 3. Human Approval

No code until the human signs off.

### 4. Plan & Implement

Break the approved spec into small, verifiable tasks.

> [!TIP]
> Use `/plan` to invoke the `planning-and-task-breakdown` skill.

## Rationalizations vs. Reality

| Rationalization | Reality |
|---|---|
| "This is simple, no spec needed" | Simple tasks still need acceptance criteria. A two-line spec is fine. |
| "I'll write the spec after" | That's documentation, not specification. Value is in forcing clarity *before* code. |
| "The spec will slow us down" | 15-minute spec prevents hours of rework. |
| "Requirements will change anyway" | That's why it's a living document. Outdated spec beats no spec. |

## Red Flags

- Starting code without written requirements
- Implementing features not in the spec
- Architectural decisions made but not documented
- Skipping spec because task seems "obvious"

## Verification

- [ ] Spec covers: objectives, scope, structure, testing, boundaries
- [ ] Human has reviewed and approved
- [ ] Success criteria are specific, measurable, testable
- [ ] Constraints explicitly defined
- [ ] Spec persisted (artifact, vault, or repo document such as `SPEC.md`)
