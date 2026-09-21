# Feature Spec: Integrate Latest git-signoff (v0.5.0 / verify-v1.7)

**Feature Slug:** `integrate-git-signoff-48d1c2`  
**Target Branch:** `origin/main`  
**Date:** 2026-09-21  

---

## 1. Overview & Objectives

Integrate the latest release of [`jerrylin96/git-signoff`](https://github.com/jerrylin96/git-signoff) (v0.5.0 / `verify-v1.7` / `init-v10`) into `dotagent` (`jerrylin96/dotagent`).

### Objectives:
1. **Adopt Single Deterministic Stdlib Architecture**: Replace the legacy `signoff_mcp/` server package with `skills/git-signoff/attest.py` (zero-dependency Python 3.10+ standard library script).
2. **Clean Migration to `git-signoff`**: Rename the skill directory from `skills/signoff` to `skills/git-signoff` and update all slash commands and references across `dotagent` from `/signoff` to `/git-signoff` (no legacy `/signoff` alias per user instruction).
3. **Upgrade Verification Gate**: Update GitHub Actions workflow from `jerrylin96/signoff/verify@verify-v1.1` to `jerrylin96/git-signoff/verify@verify-v1.7`.
4. **Modernize Subtree Synchronization**: Update `scripts/sync_signoff_subtree.sh` to track `https://github.com/jerrylin96/git-signoff` with prefixes `skills/git-signoff` and `conformance`, ensuring future upgrades are single-command deterministic.
5. **Port Test Suite & Modernize Contract Tests**: Port unit tests for `attest.py` into `scripts/tests/` and update `scripts/tests/test_skill_references.py` contract tests to assert against `skills/git-signoff/SKILL.md` and `attest.py`.

---

## 2. Scope & Detailed File Changes

### A. Subtree & Skill Files
- **Delete `skills/signoff/`** and vendor upstream `skills/git-signoff/` (carrying `SKILL.md`, `attest.py`, `verify_signoff.py`, `HARNESSES.md`, `specs/`, `profiles/`, `LICENSE`).
- **Sync `conformance/`** from upstream `git-signoff@main`.
- **Remove `signoff_mcp/`**: Entire legacy directory deleted.
- **Update Symlink**: Update `.claude/skills/` to point `.claude/skills/git-signoff` to `../../skills/git-signoff`. Remove stale `.claude/skills/signoff`.

### B. Subtree Sync Script
- In `scripts/sync_signoff_subtree.sh`:
  - Change default upstream repository from `https://github.com/jerrylin96/signoff` to `https://github.com/jerrylin96/git-signoff`.
  - Update prefixes loop to iterate over `skills/git-signoff` and `conformance` (dropping `signoff_mcp`).

### C. Repository Configuration & Packaging
- **`pyproject.toml`**:
  - Remove `signoff-mcp = "signoff_mcp.server:main"` from `[project.scripts]`.
  - Remove `signoff_mcp*` from `[tool.setuptools.packages.find] include`.
- **`pytest.ini`**:
  - Remove `signoff_mcp/tests` from `testpaths` (retaining `scripts/tests` and `skills`).
- **`.github/workflows/signoff.yml`**:
  - Update action reference from `jerrylin96/signoff/verify@verify-v1.1` to `jerrylin96/git-signoff/verify@verify-v1.7`.

### D. Documentation & Command References
- **`AGENTS.md` / `GEMINI.md`**:
  - Update slash command table: `/signoff` $\rightarrow$ `/git-signoff`, link `[git-signoff](skills/git-signoff/SKILL.md)`.
  - Update Section 4 discoverable skills list and Section 3 lifecycle references to `/git-signoff`.
- **`skills/make-feature/SKILL.md`**:
  - Update Step 8 and recommendations from `/signoff` to `/git-signoff`.
- **`skills/math-proof-audit/SKILL.md`**:
  - Update Phase 3 references from `/signoff` and `@skill:signoff` to `/git-signoff` and `@skill:git-signoff`.

### E. Test Suites
- **`scripts/tests/test_skill_references.py`**:
  - Update skill resolution tests to expect `skills/git-signoff` with frontmatter `name: git-signoff`.
  - Update `test_signoff_socratic_remediation_rule`, `test_signoff_gsa_protocol_spec_and_trailers`, and `test_signoff_phase3c_interview_contract` to check `skills/git-signoff/` and adapt to `attest.py` mechanical invocation conventions.
- **`scripts/tests/test_attest.py`**:
  - Port upstream's unit tests for `attest.py` (adapters, notes merge, profile resolution, commit preparation).

---

## 3. Boundaries & Non-Goals

- **Non-Goal**: Retaining legacy `/signoff` backward-compatibility aliases or shims. Per user instruction, clean migration to `git-signoff` everywhere.
- **Non-Goal**: Modifying upstream `git-signoff` protocol semantics. Upstream `attest.py` and `verify_signoff.py` are vendored directly as canonical implementations.
- **Non-Goal**: Running `init.py` inside this repository. Subtree synchronization and isolated worktree commits supersede leaf initializer runs.

---

## 4. Verification & Acceptance Criteria

1. **Clean Test Run**: `pytest` passes 100% across `scripts/tests` and `skills`.
2. **Lint & Code Health**: `ruff check .` passes with zero violations.
3. **Subtree Verification**: `scripts/sync_signoff_subtree.sh` runs cleanly without drift errors against `https://github.com/jerrylin96/git-signoff`.
4. **No Legacy References**: Zero occurrences of `signoff_mcp` in `pyproject.toml`, `pytest.ini`, or active scripts. Zero broken `@skill:signoff` references in `skills/`.
5. **CI Gate Readiness**: `.github/workflows/signoff.yml` references canonical `jerrylin96/git-signoff/verify@verify-v1.7`.
