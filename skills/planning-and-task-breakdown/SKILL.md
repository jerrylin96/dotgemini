---
name: planning-and-task-breakdown
description: Decompose specs into small, verifiable tasks with acceptance criteria and dependency ordering. Maps to the /plan command.
---

## Overview

Transforms a specification or feature request into granular, actionable, testable units of work.

## When to Use

- Spec exists but needs implementable units
- Task feels too large or complex to start
- Work needs parallelization
- Need to communicate scope

## When NOT to Use

- Simple, single-file changes where scope is already obvious

## Process

### Step 1: Enter Plan Mode

Operate in **read-only** mode:

- Read the spec and relevant codebase sections
- Identify existing patterns and conventions
- Map dependencies between components
- Note risks and unknowns
- Do NOT write code during planning

> [!TIP]
> **(Antigravity Only)** Use a `research` subagent for codebase exploration. This keeps the main agent's context clean for planning decisions. In other runtimes, do this exploration directly.

### Step 2: Decomposition

- Break objective into atomic tasks
- **The "5-File" Rule**: each task touches ~5 files or fewer
- If a task can't be described in a few bullet points, break it down further
- Identify and sequence dependencies

> [!TIP]
> **(Antigravity Only)** For parallelizable slices, use `self` subagents with `Workspace: branch`. Each subagent gets its own git branch to implement a slice concurrently.

### Step 3: Output

- Create the plan as a reviewable document with a checklist for tracking progress
- Every task must include acceptance criteria and a verify step

> [!TIP]
> **(Antigravity Only)** Store the plan as an artifact with `RequestFeedback: true` in `<appDataDir>/brain/<conversation-id>/`. In other runtimes, write `tasks/plan.md` in the repo.


## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I can hold the plan in my head" | Context windows are finite; externalizing prevents hallucinations |
| "This is too simple to need a plan" | Simple tasks hide complexity; quick breakdown ensures alignment |
| "I'll add tests/documentation later" | You won't. Do it while context is fresh |
| "I can skip planning and just start coding" | Leads to scope creep, architectural drift, and rework |
| "I will plan as I go" | Agent loses focus without pre-defined roadmap |

## Red Flags

- Implementing code before plan is finalized
- Vague task definitions ("Implement feature") instead of verifiable units
- Plan ignores existing codebase patterns
- Tasks lack acceptance criteria

## Verification

- [ ] Plan exists as artifact and covers full scope
- [ ] Tasks are clear, atomic, and ordered
- [ ] Acceptance criteria defined for every task
- [ ] Every task has verification step
- [ ] Dependencies identified and ordered
- [ ] No task touches >5 files
- [ ] Checkpoints between major phases
- [ ] Plan reviewed via `RequestFeedback` gate
