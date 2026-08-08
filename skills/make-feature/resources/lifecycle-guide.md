# Lifecycle Reference Guide

Quick reference for `/make-feature` milestone gates and associated slash commands.

*For complete execution instructions and worktree rules, see [make-feature/SKILL.md](../SKILL.md).*

---

## Single Mandatory Pipeline

All codebase modifications (features, bug fixes, refactors, config edits, and skill updates) follow the unified `/make-feature` sequential milestone pipeline without exception:

1. **Stage 0 (Interactive Alignment)**: Conduct interactive Q&A (`/grillme`) to resolve unknowns and scope.
2. **Phase 1a (Spec & Spec Review)**: Draft `/spec`, run `Adversarial Spec Reviewer` subagent loop until `APPROVE`. **PAUSE** for explicit human approval.
3. **Phase 1b (Plan & Plan Review)**: Draft `/plan`, run `Adversarial Plan Reviewer` subagent loop until `APPROVE`. **PAUSE** for explicit human approval.
4. **Phase 2 (Build & RED Test Review)**: Create isolated worktree branch (`gemini/<feature-name>`), write RED test suite, run `Adversarial Test Reviewer` subagent loop until `APPROVE`, write GREEN code, test via `run_in_env.py`, commit locally.
5. **Phase 3 (Push & Code Review)**: Push feature branch to `origin` and run `Adversarial Code Reviewer` subagent loop until `APPROVE`.
6. **Phase 4 (Human Signoff & Merge)**: **PAUSE**. Present review report to human engineer. Merge only upon explicit user confirmation.

---

## Gate-to-Skill Mapping

| Gate | Slash Command / Role | Skill | What It Produces |
|---|---|---|---|
| **Align** | `/grillme` | [spec-driven-development](../../spec-driven-development/SKILL.md) | Clarified scope & user constraints |
| **Spec** | `/spec` | [spec-driven-development](../../spec-driven-development/SKILL.md) | Requirements artifact (Pauses for human approval) |
| **Spec Review** | `Adversarial Spec Reviewer` | [adversarial-review](../../adversarial-review/SKILL.md) | Verified spec free of scope gaps & ambiguity |
| **Plan** | `/plan` | [planning-and-task-breakdown](../../planning-and-task-breakdown/SKILL.md) | Ordered task list (Pauses for human approval) |
| **Plan Review** | `Adversarial Plan Reviewer` | [adversarial-review](../../adversarial-review/SKILL.md) | Verified plan with atomic tasks & TDD targets |
| **Build** | `/build` | [incremental-implementation](../../incremental-implementation/SKILL.md) | Working code in thin vertical slices |
| **Test** | `/test` | [test-driven-development](../../test-driven-development/SKILL.md) | RED test suite proving requirements |
| **RED Test Review** | `Adversarial Test Reviewer` | [adversarial-review](../../adversarial-review/SKILL.md) | Verified test suite with rigorous assertions |
| **Code Review** | `Adversarial Code Reviewer` | [adversarial-review](../../adversarial-review/SKILL.md) | Subagent review loop on pushed branch |
| **Explain Diff** | `/explain-diff` | [explain-diff](../../explain-diff/SKILL.md) | Interactive, neutral changeset walkthrough |
| **Signoff** | `/signoff` | [signoff](../../signoff/SKILL.md) | Socratic reverse-interview before merge |
| **Debug** | — | [debugging-and-error-recovery](../../debugging-and-error-recovery/SKILL.md) | Root-cause fix (invoke when tests fail) |
| **Simplify** | `/code-simplify` | [ponytail](../../ponytail/SKILL.md) | Reduced complexity (Ponytail philosophy) |
