# Lifecycle Guide

Reference for determining which lifecycle gates to apply based on change complexity.

*Skills adapted from [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills).*

## Complexity Heuristic

Assess before starting work. Pick the first tier that fits:

| Tier | Signals | Gates |
|---|---|---|
| **Trivial** | Config tweak, typo, docs-only, ≤5 lines | build → test → commit |
| **Small** | Single-file logic change, clear scope | plan → build → test → review → commit |
| **Medium** | Multi-file feature, new behavior | spec → plan → build (incremental) → test → review → commit |
| **Large** | Architecture change, new subsystem, cross-cutting | spec → plan → build (sliced) → test → review → simplify → commit |

> [!IMPORTANT]
> When in doubt, tier UP, not down. Skipping a gate is a one-way door — you can't retroactively add a spec after building the wrong thing.

## Unified Gate Progression & Sequential Pauses

All codebase modifications follow the unified `/make-feature` sequential step pipeline:

1. **Step 1 (Resolve Branch)**: Identify target base branch (`<base_branch>`) and feature name (`gemini/<feature-name>`).
2. **Step 2 (`/spec` Gate)**: Draft spec artifact → **PAUSE for explicit human approval**.
3. **Step 3 (`/plan` Gate)**: Draft plan artifact → **PAUSE for explicit human approval**.
4. **Step 4 (Build & Test)**: Worktree setup, code implementation, test execution via `run_in_env.py`.
5. **Step 5 (Stage, Commit & Push)**: Commit worktree changes and push to `origin`.
6. **Step 6 (Adversarial Review Loop)**: Subagent review loop until `APPROVE` verdict with 0 open critical findings.
7. **Step 7 (Human Review & Signoff Gate)**: **PAUSE for human merge decision**. Recommended tools: [/explain-diff](../../explain-diff/SKILL.md) and [/signoff](../../signoff/SKILL.md).

## Gate-to-Skill Mapping

| Gate | Slash Command | Skill | What It Produces |
|---|---|---|---|
| **Spec** | `/spec` | [spec-driven-development](../../spec-driven-development/SKILL.md) | Requirements artifact (Pauses for human approval) |
| **Plan** | `/plan` | [planning-and-task-breakdown](../../planning-and-task-breakdown/SKILL.md) | Ordered task list (Pauses for human approval) |
| **Build** | `/build` | [incremental-implementation](../../incremental-implementation/SKILL.md) | Working code in thin vertical slices |
| **Test** | `/test` | [test-driven-development](../../test-driven-development/SKILL.md) | Passing tests that prove correctness |
| **Review** | `/review` | [adversarial-review](../../adversarial-review/SKILL.md) | Subagent review loop on pushed branch |
| **Explain Diff** | `/explain-diff` | [explain-diff](../../explain-diff/SKILL.md) | Interactive, neutral changeset walkthrough |
| **Signoff** | `/signoff` | [signoff](../../signoff/SKILL.md) | Socratic reverse-interview before merge |
| **Debug** | — | [debugging-and-error-recovery](../../debugging-and-error-recovery/SKILL.md) | Root-cause fix (invoke when tests fail) |
| **Simplify** | `/code-simplify` | [ponytail](../../ponytail/SKILL.md) | Reduced complexity (Ponytail philosophy) |

## Anti-Rationalization Guardrail

Before skipping any gate, check the **Common Rationalizations** table in that gate's skill. If your reason for skipping appears in the table, you're rationalizing — follow the gate.

## Exit Criteria Summary

Each gate is complete when its skill's **Verification** checklist is satisfied. Key checkpoints:

- **Spec done** → Human reviewed and explicitly approved `/spec` artifact (Step 2)
- **Plan done** → Human reviewed and explicitly approved `/plan` artifact (Step 3)
- **Build done** → Each slice tested and verified in worktree (Step 4)
- **Test done** → All unit tests pass cleanly via `run_in_env.py` (Step 4)
- **Review done** → Subagent adversarial review loop resolved with `APPROVE` verdict (Step 6)
- **Signoff & Merge done** → Human engineer reviews report (using optional `/explain-diff` and `/signoff`) and authorizes/executes merge into `<base_branch>` (Step 7)
