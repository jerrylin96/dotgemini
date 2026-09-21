# Feature Spec: Integrate Latest git-signoff (v0.5.0 / verify-v1.7)

**Feature Slug:** `integrate-git-signoff-48d1c2`  
**Target Branch:** `origin/main`  
**Date:** 2026-09-21  

---

## 1. Overview & Objectives

Integrate the latest release of [`jerrylin96/git-signoff`](https://github.com/jerrylin96/git-signoff) (v0.5.0 / `verify-v1.7` / `init-v10`) into `dotagent` (`jerrylin96/dotagent`).

### Objectives:
1. **Adopt Single Deterministic Stdlib Architecture**: Replace the legacy `signoff_mcp/` server package with `skills/git-signoff/attest.py` (zero-dependency Python 3.10+ standard library script).
2. **Clean Migration to `git-signoff`**: Rename the skill directory from `skills/signoff` to `skills/git-signoff` and update all slash commands and references across `dotagent` from `/signoff` to `/git-signoff` with zero broken links or legacy aliases.
3. **Upgrade Verification Gate**: Update GitHub Actions workflow from `jerrylin96/signoff/verify@verify-v1.1` to `jerrylin96/git-signoff/verify@verify-v1.7`.
4. **Modernize Subtree Synchronization & Drift Guard**: Update `scripts/sync_signoff_subtree.sh` to track `https://github.com/jerrylin96/git-signoff` with prefixes `skills/git-signoff` and `conformance`, handling re-adoption cleanly while preserving the `upstream_tree == local_tree` drift invariant (zero local mutations in vendored subtree).
5. **Port Test Suite & Modernize Contract Tests**: Port unit tests for `attest.py` into `scripts/tests/` (using dynamic loader for hyphenated path `skills/git-signoff`) and update `scripts/tests/test_skill_references.py` contract tests to assert against `skills/git-signoff/SKILL.md`, `specs/gsa-core.md`, and `attest.py`.

---

## 2. Scope & Detailed File Changes

### A. Subtree & Skill Files
- **Retire Legacy Subtrees**: Run `git rm -r skills/signoff signoff_mcp` to purge legacy directories.
- **Adopt `skills/git-signoff/`**: Adopt `skills/git-signoff/` from `jerrylin96/git-signoff@main` (carrying `SKILL.md`, `attest.py`, `verify_signoff.py`, `HARNESSES.md`, `specs/`, `profiles/`, `LICENSE`).
- **Sync/Re-adopt `conformance/`**: Re-sync `conformance/` from `jerrylin96/git-signoff@main`. If squash ancestor divergence occurs between remote URLs, re-adopt prefix via `git subtree add --prefix=conformance --squash`.
- **Subtree Drift Invariant**: Vendored subtree directories (`skills/git-signoff` and `conformance`) must have 100% byte-for-byte tree identity with upstream (`upstream_tree == local_tree`). Zero local modifications are permitted inside vendored paths.
- **Update Symlink**: Remove stale `.claude/skills/signoff` symlink and create `.claude/skills/git-signoff` pointing to `../../skills/git-signoff`.

### B. Subtree Sync Script
- In `scripts/sync_signoff_subtree.sh`:
  - Change default upstream repository to `https://github.com/jerrylin96/git-signoff`.
  - Update prefixes loop to iterate over `skills/git-signoff` and `conformance` (dropping `signoff_mcp`).
  - Add squash lineage divergence fallback: if `git subtree merge` fails due to unrelated histories across the repo rename, clean and re-adopt the prefix using `git subtree add`.

### C. Repository Configuration & Packaging
- **`pyproject.toml`**:
  - Remove `signoff-mcp = "signoff_mcp.server:main"` from `[project.scripts]`.
  - Remove `signoff_mcp*` from `[tool.setuptools.packages.find] include`.
  - Remove `mcp = ["mcp"]` from `[project.optional-dependencies]` (as `signoff_mcp` was its sole consumer).
- **`pytest.ini`**:
  - Remove `signoff_mcp/tests` from `testpaths` (retaining `scripts/tests` and `skills`).
- **`.github/workflows/signoff.yml`**:
  - Update action reference from `jerrylin96/signoff/verify@verify-v1.1` to `jerrylin96/git-signoff/verify@verify-v1.7`.

### D. Documentation & Command References
- **`README.md`**:
  - Update Section 3 skill table and descriptions from `/signoff` to `/git-signoff`.
- **`AGENTS.md` / `GEMINI.md`**:
  - Update slash command table: `/signoff` $\rightarrow$ `/git-signoff`, link `[git-signoff](skills/git-signoff/SKILL.md)`.
  - Update Section 4 discoverable skills list and Section 3 lifecycle references to `/git-signoff`.
- **`skills/make-feature/SKILL.md`**:
  - Update Step 7b (line 254) and Step 8 (line 273) from `/signoff` to `/git-signoff`.
- **`skills/make-feature/resources/lifecycle-guide.md`**:
  - Update Step 8 references and link from `[signoff](../../signoff/SKILL.md)` to `[git-signoff](../../git-signoff/SKILL.md)`.
- **`skills/catchmeup/SKILL.md`**:
  - Update line 34 link from `[/signoff](../signoff/SKILL.md)` to `[/git-signoff](../git-signoff/SKILL.md)`.
- **`skills/math-proof-audit/SKILL.md`**:
  - Update Phase 3 references from `/signoff` and `@skill:signoff` to `/git-signoff` and `@skill:git-signoff`.

### E. Test Suites
- **`scripts/tests/test_skill_references.py`**:
  - Update skill resolution tests to expect `skills/git-signoff` with frontmatter `name: git-signoff`.
  - Modernize contract assertions:
    - `test_signoff_socratic_remediation_rule`: assert Socratic remediation, evaluation, uncertainty handling, and explain-diff references against `skills/git-signoff/SKILL.md` and `skills/math-proof-audit/SKILL.md`.
    - `test_signoff_gsa_protocol_spec_and_trailers`: assert GSA v1.0 trailers, notes references, and `cat_sort_uniq` across `skills/git-signoff/specs/gsa-core.md` and `skills/git-signoff/attest.py` (rather than expecting mechanical bash commands in `SKILL.md`).
    - `test_signoff_phase3c_interview_contract`: target `skills/git-signoff/` paths (`HARNESSES.md`, `profiles/`, `SKILL.md`).
- **`scripts/tests/_attest_loader.py` & `scripts/tests/test_attest.py`**:
  - Adopt dynamic import helper `_attest_loader.py` (using `importlib.util.spec_from_file_location`) to safely import `skills/git-signoff/attest.py` despite the hyphenated path.
  - Port upstream unit tests for `attest.py` (adapters, notes merge, profile resolution, commit preparation).

---

## 3. Boundaries & Non-Goals

- **Non-Goal**: Retaining legacy `/signoff` backward-compatibility aliases or shims. Per user instruction, clean migration to `git-signoff` everywhere.
- **Non-Goal**: Modifying upstream `git-signoff` protocol semantics. Upstream `attest.py` and `verify_signoff.py` are vendored directly as canonical implementations without local edits.
- **Non-Goal**: Running `init.py` inside this repository. Subtree synchronization and isolated worktree commits supersede leaf initializer runs.

---

## 4. Verification & Acceptance Criteria

1. **Clean Test Run**: `pytest` passes 100% across `scripts/tests` and `skills`.
2. **Lint & Code Health**: `ruff check .` passes with zero violations.
3. **Subtree Verification**: `scripts/sync_signoff_subtree.sh` runs cleanly without drift errors against `https://github.com/jerrylin96/git-signoff` (`upstream_tree == local_tree`).
4. **No Legacy References**:
   - Zero occurrences of `signoff_mcp` in `pyproject.toml`, `pytest.ini`, or active scripts.
   - Zero occurrences of broken `@skill:signoff` references or dead relative links to `skills/signoff` in any tracked markdown file.
5. **CI Gate Readiness**: `.github/workflows/signoff.yml` references canonical `jerrylin96/git-signoff/verify@verify-v1.7`.
