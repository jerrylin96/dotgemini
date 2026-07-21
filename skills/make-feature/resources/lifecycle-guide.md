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

## Gate-to-Skill Mapping

| Gate | Slash Command | Skill | What It Produces |
|---|---|---|---|
| **Spec** | `/spec` | [spec-driven-development](../../spec-driven-development/SKILL.md) | Requirements artifact with acceptance criteria |
| **Plan** | `/plan` | [planning-and-task-breakdown](../../planning-and-task-breakdown/SKILL.md) | Ordered task list with verification steps |
| **Build** | `/build` | [incremental-implementation](../../incremental-implementation/SKILL.md) | Working code in thin vertical slices |
| **Test** | `/test` | [test-driven-development](../../test-driven-development/SKILL.md) | Passing tests that prove correctness |
| **Review** | `/review` | [code-review-and-quality](../../code-review-and-quality/SKILL.md) (Small) / [adversarial-review](../../adversarial-review/SKILL.md) (Medium/Large) | Five-axis review verdict (subagent-isolated for Medium/Large) |
| **Debug** | — | [debugging-and-error-recovery](../../debugging-and-error-recovery/SKILL.md) | Root-cause fix (invoke when tests fail) |
| **Simplify** | `/code-simplify` | [ponytail](../../ponytail/SKILL.md) | Reduced complexity (Ponytail philosophy) |

## Anti-Rationalization Guardrail

Before skipping any gate, check the **Common Rationalizations** table in that gate's skill. If your reason for skipping appears in the table, you're rationalizing — follow the gate.

## Exit Criteria Summary

Each gate is complete when its skill's **Verification** checklist is satisfied. Don't advance to the next gate until the current one passes. Key checkpoints:

- **Spec done** → Human reviewed, acceptance criteria testable, boundaries defined
- **Plan done** → Tasks atomic, ordered, each has acceptance criteria and verify step
- **Build done** → Each slice tested and verified before next slice
- **Test done** → All tests pass, no regressions, edge cases covered
- **Review done** → Five-axis review complete (subagent adversarial review for Medium/Large per make-feature Step 6), verdict rendered, no CRITICAL findings open
