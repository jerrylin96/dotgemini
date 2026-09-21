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
3. **Upgrade Verification Gate & Permissions**: Update GitHub Actions workflow from `jerrylin96/signoff/verify@verify-v1.1` to `jerrylin96/git-signoff/verify@verify-v1.7`, explicitly configuring `contents: read` and `pull-requests: read` so scan-refs can verify squash and rebase PR merges.
4. **Modernize Subtree Synchronization & Drift Guard**: Update `scripts/sync_signoff_subtree.sh` to track `https://github.com/jerrylin96/git-signoff` with prefixes `skills/git-signoff` and `conformance`, handling re-adoption cleanly while preserving the `upstream_tree == local_tree` drift invariant (zero local mutations in vendored subtree).
5. **Comprehensive Test Port & Contract Modernization**: Port the complete suite of upstream unit tests, test helpers, and fixtures for `attest.py` into `scripts/tests/` with strict environment isolation, and update `scripts/tests/test_skill_references.py` contract tests to assert against `skills/git-signoff/SKILL.md` (including the Worktree Target Mandate), `specs/gsa-core.md`, and `attest.py`.

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

### C. Repository Configuration & CI Workflow
- **`pyproject.toml`**:
  - Remove `signoff-mcp = "signoff_mcp.server:main"` from `[project.scripts]`.
  - Remove `signoff_mcp*` from `[tool.setuptools.packages.find] include`.
  - Remove `mcp = ["mcp"]` from `[project.optional-dependencies]` (as `signoff_mcp` was its sole consumer).
- **`pytest.ini`**:
  - Remove `signoff_mcp/tests` from `testpaths` (retaining `scripts/tests` and `skills`).
- **`.github/workflows/signoff.yml`**:
  - Update action reference from `jerrylin96/signoff/verify@verify-v1.1` to `jerrylin96/git-signoff/verify@verify-v1.7`.
  - **Add Mandatory Permissions Block**:
    ```yaml
    permissions:
      contents: read
      pull-requests: read   # scan-refs: allows discovering PR attestation evidence for squash/rebase merges
    ```

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

### E. Test Suites & Port Inventory
- **`scripts/tests/test_skill_references.py`**:
  - Update skill resolution tests to expect `skills/git-signoff` with frontmatter `name: git-signoff`.
  - Modernize contract assertions:
    - `test_signoff_socratic_remediation_rule`: assert Socratic remediation, evaluation, uncertainty handling, explain-diff references, and the **Worktree Target Mandate** (`worktree_path`) against `skills/git-signoff/SKILL.md` (which preserves these exact contracts in v0.5.0) and `skills/math-proof-audit/SKILL.md`.
    - `test_signoff_gsa_protocol_spec_and_trailers`: assert GSA v1.0 trailers, notes references, and `cat_sort_uniq` across `skills/git-signoff/specs/gsa-core.md` and `skills/git-signoff/attest.py`.
    - `test_signoff_phase3c_interview_contract`: target `skills/git-signoff/` paths (`HARNESSES.md`, `profiles/`, `SKILL.md`).
- **Comprehensive Test Port Inventory (replacing `signoff_mcp/tests`)**:
  - **Helpers & Fixtures**:
    - `scripts/tests/_attest_loader.py`: Dynamic import of `skills/git-signoff/attest.py` via `importlib.util.spec_from_file_location` to handle hyphenated paths safely.
    - `scripts/tests/helpers.py`: Isolated git repo fixture builders (`init_repo`, `commit_file`) with explicit user credentials (`user.name`, `user.email`) to prevent leaking into or depending on host git config.
    - `scripts/tests/conftest.py`: Pytest session configuration ensuring dynamic environment isolation.
    - `scripts/tests/fixtures/production_attestation.txt`: Ground-truth production vector attestation fixture.
  - **Test Modules**:
    - `scripts/tests/test_attest.py`: Core attestation mechanics (prepare, marker, commit, rollback, notes push, failure exit codes).
    - `scripts/tests/test_attest_adapters.py`: Harness transcript adapters (Antigravity, Claude Code, Codex, generic).
    - `scripts/tests/test_attest_notes_merge.py`: Notes merge (`cat_sort_uniq`) and tracking ref concurrency handling.
    - `scripts/tests/test_attest_profile.py`: Profile resolution, science signal detection, and marker hashing.
    - `scripts/tests/test_production_vector.py`: Regression verification against frozen production attestation vector.
    - `scripts/tests/test_learning_modes.py`: Verification of `--explain` and `--practice` learning sessions and session guards.

---

## 3. Boundaries & Non-Goals

- **Non-Goal**: Retaining legacy `/signoff` backward-compatibility aliases or shims. Per user instruction, clean migration to `git-signoff` everywhere.
- **Non-Goal**: Modifying upstream `git-signoff` protocol semantics. Upstream `attest.py` and `verify_signoff.py` are vendored directly as canonical implementations without local edits.
- **Non-Goal**: Running `init.py` inside this repository. Subtree synchronization and isolated worktree commits supersede leaf initializer runs.

---

## 4. Verification & Acceptance Criteria

1. **Clean Test Run**: `pytest` passes 100% across all ported test modules in `scripts/tests` and `skills`.
2. **Lint & Code Health**: `ruff check .` passes with zero violations across all ported tests and modified scripts.
3. **Subtree Verification**: `scripts/sync_signoff_subtree.sh` runs cleanly without drift errors against `https://github.com/jerrylin96/git-signoff` (`upstream_tree == local_tree`).
4. **No Legacy References**:
   - Zero occurrences of `signoff_mcp` in `pyproject.toml`, `pytest.ini`, or active scripts.
   - Zero occurrences of broken `@skill:signoff` references or dead relative links to `skills/signoff` in any tracked markdown file.
5. **CI Gate Readiness**: `.github/workflows/signoff.yml` references canonical `jerrylin96/git-signoff/verify@verify-v1.7` with `contents: read` and `pull-requests: read` permissions.
