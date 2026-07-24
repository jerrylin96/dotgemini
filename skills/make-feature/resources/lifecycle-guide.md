# Lifecycle Reference Guide

Quick reference for `/make-feature` milestone gates and associated slash commands.

*For complete execution instructions and worktree rules, see [make-feature/SKILL.md](../SKILL.md).*

---

## Single Mandatory Pipeline

All codebase modifications (features, bug fixes, refactors, config edits, and skill updates) follow the unified `/make-feature` sequential 4-milestone pipeline without exception:

1. **Phase 1 (Spec & Plan)**: Draft `/spec` and `/plan` artifacts. **PAUSE** for explicit human approval.
2. **Phase 2 (Build & Worktree)**: Create isolated worktree branch (`gemini/<feature-name>`), implement edits, test via `run_in_env.py`, and commit locally.
3. **Phase 3 (Push & Adversarial Review)**: Push feature branch to `origin` and invoke background `self` subagent for `/adversarial-review` loop.
4. **Phase 4 (Human Signoff & Merge)**: **PAUSE**. Present review report to human engineer. Merge only upon explicit user confirmation prompt.

---

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
