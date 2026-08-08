---
name: spec-driven-development
description: Creates specs before coding. Maps to `/spec`. Use when starting a new project, feature, or significant change and no specification exists yet.
---

## Overview

Write the spec before the code. Every non-trivial change follows the unified [make-feature](../make-feature/SKILL.md) pipeline — after drafting the `/spec` artifact, the agent **pauses for explicit human approval** before advancing to `/plan`.

## When to Use

- Starting a new project or feature
- Significant refactoring or architectural changes
- Requirements are unclear or undocumented

## Process

### 1. Stage 0: Clarify Requirements (`/grill-me`)

Define what to build. Identify ambiguities, missing requirements, assumptions.

> [!TIP]
> Use `/grill-me` to run an interactive interview until you hit ~95% confidence on scope, non-negotiables, technical constraints, and edge cases before drafting the spec. (When executing under `/make-feature`, Stage 0 is the interactive alignment gate; for standalone spec usage or trivial typo edits, self-clarification is sufficient).

### 2. Draft the Spec

Cover: **Objectives**, **Scope**, **Project Structure**, **Code Style**, **Testing Strategy**, **Boundaries** (non-goals, constraints).

> [!TIP]
> Store the spec as an artifact with `RequestFeedback: true` so the human gets a review prompt, or persist in an Obsidian vault per `AGENTS.md §9`.

### 2b. Subagent Adversarial Spec Review

When executing under `/make-feature` Phase 1a, parent agent invokes `invoke_subagent` (`TypeName: self`, `Role: Adversarial Spec Reviewer`). Subagent audits `/spec` for unstated assumptions, missing edge cases, security/architectural risks, and scope creep until `APPROVE`. (For standalone spec usage outside `/make-feature`, self-review checklist is sufficient).

### 3. Human Approval (Sequential Pause)

**PAUSE**: Do not write code or advance to `/plan` until the human engineer explicitly approves the audited spec (`make-feature` Step 2c).

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
- [ ] Human has reviewed and explicitly approved spec (`make-feature` Step 2c pause)
- [ ] Success criteria are specific, measurable, testable
- [ ] Constraints explicitly defined
- [ ] Spec persisted (artifact, vault, or repo document such as `SPEC.md`)
