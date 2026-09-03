# Lifecycle Reference Guide

Quick reference for `/make-feature` milestone gates and associated slash commands.

*For complete execution instructions and worktree rules, see [make-feature/SKILL.md](../SKILL.md).*

---

## Single Mandatory Pipeline

All codebase modifications (features, bug fixes, refactors, config edits, and skill updates) follow the unified `/make-feature` sequential milestone pipeline without exception:

1. **Stage 0 (Interactive Alignment Gate)**: Conduct interactive Q&A (`/grill-me`) to clarify non-negotiables, edge cases, and scope boundaries before drafting `/spec`.
2. **Phase 1a (Spec & Spec Review Gate)**: Create isolated worktree branch (`gemini/<feature-name>-<hash>`) under `~/.gemini/tmp/worktrees/`, draft in-tree spec `<feature-name>-<hash>/spec.md` (superseding `/artifact` and Obsidian), commit and push to `origin` for remote review, run subagent `Adversarial Spec Reviewer` loop until `APPROVE`, **PAUSE** for explicit human approval (or trigger early abort teardown on rejection).
3. **Phase 1b (Plan & Plan Review Gate)**: Draft in-tree plan `<feature-name>-<hash>/plan.md` with explicit TDD targets, commit and push to `origin`, run subagent `Adversarial Plan Reviewer` loop until `APPROVE`, **PAUSE** for explicit human approval (or trigger early abort teardown on rejection).
4. **Phase 2 (Build, Worktree & RED Test Remote Push Gate)**: Write RED test suite, run subagent `Adversarial Test Reviewer` loop until `APPROVE`, stage, commit, and push failing RED test suite to `origin` (`test: add RED test suite (failing)`), implement GREEN code, and verify 100% test pass via `run_in_env.py`. (In Heavy Mode, enforce a per-slice 2-stage commit cadence: `test(slice-N)` pushed → `feat(slice-N)` pushed).
5. **Phase 3 (Push, Adversarial Code Review Gate & Ephemeral Cleanup)**: Push GREEN code to `origin`, run subagent `Adversarial Code Reviewer` loop until `APPROVE`, execute idempotent ephemeral folder cleanup (`git rm -rf --ignore-unmatch "<feature-name>-<hash>"`), and generate post-review audit report artifact strictly within conversation brain (prohibiting Obsidian dumping).
6. **Phase 4 (Human Signoff, PR Creation & Manual Merge)**: **PAUSE**. Present review report to human engineer. Human engineer creates Pull Request and merges into base branch before worktree is pruned.

---

## Gate-to-Skill Mapping

| Gate | Slash Command / Role | Skill | What It Produces |
|---|---|---|---|
| **Align** | `/grill-me` | [spec-driven-development](../../spec-driven-development/SKILL.md) | Clarified scope & user constraints |
| **Spec** | `/spec` | [spec-driven-development](../../spec-driven-development/SKILL.md) | In-tree spec (`<feature-name>-<hash>/spec.md`) (Pauses for human approval) |
| **Spec Review** | `Adversarial Spec Reviewer` | [adversarial-review](../../adversarial-review/SKILL.md) | Verified spec free of scope gaps & ambiguity |
| **Plan** | `/plan` | [planning-and-task-breakdown](../../planning-and-task-breakdown/SKILL.md) | In-tree plan (`<feature-name>-<hash>/plan.md`) (Pauses for human approval) |
| **Plan Review** | `Adversarial Plan Reviewer` | [adversarial-review](../../adversarial-review/SKILL.md) | Verified plan with atomic tasks & TDD targets |
| **Build** | `/build` | [incremental-implementation](../../incremental-implementation/SKILL.md) | Working code in thin vertical slices |
| **Test** | `/test` | [test-driven-development](../../test-driven-development/SKILL.md) | RED test suite proving requirements |
| **RED Test Review** | `Adversarial Test Reviewer` | [adversarial-review](../../adversarial-review/SKILL.md) | Verified test suite with rigorous assertions |
| **Code Review** | `Adversarial Code Reviewer` | [adversarial-review](../../adversarial-review/SKILL.md) | Subagent review loop on pushed branch |
| **Explain Diff** | `/explain-diff` | [explain-diff](../../explain-diff/SKILL.md) | Interactive, neutral changeset walkthrough |
| **Signoff** | `/signoff` | [signoff](../../signoff/SKILL.md) | Socratic reverse-interview before merge |
| **Debug** | — | [debugging-and-error-recovery](../../debugging-and-error-recovery/SKILL.md) | Root-cause fix (invoke when tests fail) |
| **Simplify** | `/code-simplify` | [ponytail](../../ponytail/SKILL.md) | Reduced complexity (Ponytail philosophy) |
