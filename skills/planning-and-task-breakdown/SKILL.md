---
name: planning-and-task-breakdown
description: Decompose specs into small, verifiable tasks with acceptance criteria and dependency ordering. Maps to the /plan command.
---

## Overview

Transforms a specification or feature request into granular, actionable, testable units of work. Every non-trivial change follows the unified [make-feature](../make-feature/SKILL.md) pipeline — after drafting the plan document (in-tree `${FEATURE_SLUG}/plan.md` under `make-feature`), the agent **pauses for explicit human approval** before writing code.

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
> Use a `research` subagent for codebase exploration. This keeps the main agent's context clean for planning decisions.

### Step 2: Decomposition & TDD Task Design

- Break objective into atomic tasks
- **The "5-File" Rule**: each task touches ~5 files or fewer
- **TDD Task Schema**: Every task item MUST explicitly specify:
  1. **RED Test Spec**: The target test file and failing test assertion to write *before* touching feature code.
  2. **GREEN Implementation Target**: Minimal code to make the test pass.
  3. **Verify Command**: Exact empirical test runner command (e.g. `python3 ~/.gemini/scripts/run_in_env.py <worktree> pytest ...`).
- If a task can't be described in a few bullet points, break it down further
- Identify and sequence dependencies

> [!TIP]
> For parallelizable slices, use `self` subagents with `Workspace: branch`. Each subagent gets its own git branch to implement a slice concurrently.

### Step 2b: Execution Strategy Recommendation

Every `/plan` artifact must explicitly declare its execution strategy near the top, ensuring exactly one strategy checkbox is selected:

When Standard Single Agent is selected:
```markdown
## Execution Strategy
- [x] Standard Single Agent (Fast, atomic tasks)
- [ ] Sequential Subagents (`Workspace: inherit`) — *Recommended for 5 or more complex multi-file slices or external plan handoffs*
```

When Sequential Subagents strategy is selected:
```markdown
## Execution Strategy
- [ ] Standard Single Agent (Fast, atomic tasks)
- [x] Sequential Subagents (`Workspace: inherit`) — *Recommended for 5 or more complex multi-file slices or external plan handoffs*
```

#### Strategy Triggers & Conventions:
- **Auto-Recommendation**: Agent recommends `Sequential Subagents` if the task breakdown contains 5 or more complex multi-file slices.
- **User Override Conventions**: If user prompt includes intent signals (`heavy`, `subagent per slice`, or external plan handoff) or command invocation conventions (`/plan heavy`, `/make-feature heavy`), agent proactively selects `Sequential Subagents` execution strategy.
- **Per-Slice Review Gate**: Under `Sequential Subagents` (Heavy Mode), each slice builder subagent executes a 2-stage commit cadence: undergoes a per-slice `Adversarial Test Reviewer` gate after writing RED tests, commits and pushes `test(slice-N): add RED test suite (failing)`, and a per-slice `Adversarial Code Reviewer` gate after writing GREEN implementation before committing and pushing `feat(slice-N): implement slice N (GREEN)` and handing off to the next slice subagent.
- **External Plan Handoff Definition**: An external plan handoff refers to a plan produced outside this repository's `/plan` process, including pre-architected plans imported from frontier models.

### Step 2c: Subagent Adversarial Plan Review

When executing under `/make-feature` Phase 1b, parent agent invokes `invoke_subagent` (`TypeName: self`, `Role: Adversarial Plan Reviewer`). Subagent audits `/plan` for atomic task decomposition, explicit TDD RED/GREEN specifications, executable verify commands, dependency ordering, and worktree/env isolation safety until `APPROVE`. (For standalone plan usage outside `/make-feature`, self-review checklist is sufficient).

### Step 3: Output & Human Approval Gate

- Create the plan as a reviewable document with a checklist for tracking progress
- Every task must include TDD RED/GREEN specifications and an empirical verify step (prohibiting unverified claims).
- **PAUSE**: Do not write code until the human engineer explicitly approves the audited plan (`make-feature` Step 3c). Provide clickable links to GitHub remote file and local worktree file.

> [!IMPORTANT]
> When executing under [make-feature](../make-feature/SKILL.md) Phase 1b, the plan is written directly to `${FEATURE_SLUG}/plan.md` (e.g. `<feature-name>-<hash>/plan.md`) in the isolated worktree and committed/pushed to `origin`. This in-tree location strictly supersedes `/artifact` and Obsidian vault storage for feature development. For standalone plan usage outside git feature branches, store as an artifact with `RequestFeedback: true`.


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
- Tasks missing explicit RED test specs or empirical verification commands
- Plan ignores existing codebase patterns

## Verification

- [ ] Plan exists (in-tree `${FEATURE_SLUG}/plan.md` when using `make-feature`, superseding Obsidian/artifact paths) and covers full scope
- [ ] Tasks are clear, atomic, and ordered
- [ ] TDD RED test spec and GREEN implementation target defined for every task
- [ ] Every task has exact empirical verification command
- [ ] Dependencies identified and ordered
- [ ] No task touches >5 files
- [ ] Checkpoints between major phases
- [ ] Plan reviewed and explicitly approved by human engineer (`make-feature` Step 3c pause)

