# Implementation Plan: Integrate Latest git-signoff (v0.5.0 / verify-v1.7)

**Feature Slug:** `integrate-git-signoff-48d1c2`  
**Approved Spec:** `integrate-git-signoff-48d1c2/spec.md`  
**Target Branch:** `origin/main`  
**Date:** 2026-09-21  

---

## Execution Strategy
- [x] Standard Single Agent (Fast, atomic tasks)
- [ ] Sequential Subagents (`Workspace: inherit`) — *Recommended for 5 or more complex multi-file slices or external plan handoffs*

---

## Task Breakdown & Slices

### Slice 1: Subtree Adoption & Legacy Purge
**Goal**: Remove deprecated `signoff_mcp/` and `skills/signoff/`, update `scripts/sync_signoff_subtree.sh` to track upstream `jerrylin96/git-signoff`, adopt `skills/git-signoff/` and re-adopt `conformance/`, and update `.claude/skills/git-signoff` symlink.

- **RED Test Spec**:
  - Add assertion in `scripts/tests/test_subtree_structure.py` verifying:
    1. `skills/git-signoff/SKILL.md` and `skills/git-signoff/attest.py` exist.
    2. `conformance/vectors/` exists.
    3. `skills/signoff` and `signoff_mcp` do NOT exist in git tracking (`git ls-files`).
    4. `.claude/skills/git-signoff` points to `../../skills/git-signoff`.
- **GREEN Implementation Target**:
  - `git rm -r skills/signoff signoff_mcp`
  - Remove stale symlink `.claude/skills/signoff` and create `.claude/skills/git-signoff -> ../../skills/git-signoff`.
  - Update `scripts/sync_signoff_subtree.sh`:
    - Default `SRC="https://github.com/jerrylin96/git-signoff"`
    - Prefixes list: `skills/git-signoff` and `conformance`
    - Add squash lineage divergence fallback (re-adopt via `git subtree add` if merge base fails).
  - Adopt `skills/git-signoff` and re-adopt `conformance` via `scripts/sync_signoff_subtree.sh`.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_subtree_structure.py
  ```

---

### Slice 2: Packaging, CI Workflow & Repo Configuration
**Goal**: Clean up build configuration, remove dead MCP dependencies, update pytest configuration, and update GitHub Actions workflow with required permissions.

- **RED Test Spec**:
  - Add test in `scripts/tests/test_repo_configuration.py` asserting:
    1. `pyproject.toml` contains no `signoff-mcp` in `[project.scripts]`.
    2. `pyproject.toml` contains no `signoff_mcp*` in `packages.find include`.
    3. `pyproject.toml` contains no `mcp = ["mcp"]` in `[project.optional-dependencies]`.
    4. `pytest.ini` contains no `signoff_mcp/tests` in `testpaths`.
    5. `.github/workflows/signoff.yml` references `jerrylin96/git-signoff/verify@verify-v1.7`.
    6. `.github/workflows/signoff.yml` contains `permissions:` with `contents: read` and `pull-requests: read`.
- **GREEN Implementation Target**:
  - Edit `pyproject.toml` to remove `signoff-mcp` script, package include, and `mcp` optional dependency.
  - Edit `pytest.ini` to remove `signoff_mcp/tests` from `testpaths`.
  - Edit `.github/workflows/signoff.yml` to update the action pin and declare permissions.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_repo_configuration.py
  ```

---

### Slice 3: Command & Documentation Harmonization
**Goal**: Update all references across documentation, lifecycle guides, and skills from `/signoff` to `/git-signoff` with zero broken relative links.

- **RED Test Spec**:
  - Add assertions in `scripts/tests/test_skill_references.py` verifying:
    1. No tracked markdown file contains relative links to `skills/signoff` or dead `/signoff` links.
    2. `AGENTS.md` and `skills/make-feature/SKILL.md` reference `/git-signoff` and `skills/git-signoff/SKILL.md`.
    3. `skills/math-proof-audit/SKILL.md` references `@skill:git-signoff` and `/git-signoff`.
    4. `skills/catchmeup/SKILL.md` and `skills/make-feature/resources/lifecycle-guide.md` link to `git-signoff`.
    5. `README.md` documents `/git-signoff`.
- **GREEN Implementation Target**:
  - Update `AGENTS.md` (and symlinked `GEMINI.md`).
  - Update `README.md`.
  - Update `skills/make-feature/SKILL.md`.
  - Update `skills/make-feature/resources/lifecycle-guide.md`.
  - Update `skills/catchmeup/SKILL.md`.
  - Update `skills/math-proof-audit/SKILL.md`.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_skill_references.py -k "test_all_skill_references_resolve or test_no_broken_signoff"
  ```

---

### Slice 4: Comprehensive Test Port & Contract Modernization
**Goal**: Port full upstream unit test inventory, test helpers, and fixtures into `scripts/tests/` with environment isolation, and modernize contract assertions in `test_skill_references.py`.

- **RED Test Spec**:
  - Update `scripts/tests/test_skill_references.py` contract tests:
    - `test_all_skills_have_correct_frontmatter_name`: must validate `skills/git-signoff` with `name: git-signoff`.
    - `test_signoff_socratic_remediation_rule`: assert against `skills/git-signoff/SKILL.md` (preserving Worktree Target Mandate and `worktree_path` checks).
    - `test_signoff_gsa_protocol_spec_and_trailers`: assert GSA v1.0 trailers, notes references, and `cat_sort_uniq` across `skills/git-signoff/specs/gsa-core.md` and `skills/git-signoff/attest.py`.
    - `test_signoff_phase3c_interview_contract`: target `skills/git-signoff/` paths (`HARNESSES.md`, `profiles/`, `SKILL.md`).
  - Add test discovery for ported modules:
    - `test_attest.py`
    - `test_attest_adapters.py`
    - `test_attest_notes_merge.py`
    - `test_attest_profile.py`
    - `test_production_vector.py`
    - `test_learning_modes.py`
- **GREEN Implementation Target**:
  - Create `scripts/tests/_attest_loader.py` for dynamic import of `skills/git-signoff/attest.py`.
  - Copy isolated git helper `scripts/tests/helpers.py` and test fixture `scripts/tests/fixtures/production_attestation.txt`.
  - Port `scripts/tests/conftest.py` ensuring environment isolation (`monkeypatch`, `tmp_path`, isolated git configs).
  - Port test modules (`test_attest.py`, `test_attest_adapters.py`, `test_attest_notes_merge.py`, `test_attest_profile.py`, `test_production_vector.py`, `test_learning_modes.py`).
  - Update contract test assertions in `scripts/tests/test_skill_references.py`.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 ruff check .
  ```

---

## Acceptance Verification
1. `python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest` passes 100% (zero failures, zero regressions).
2. `python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 ruff check .` passes clean.
3. `upstream_tree == local_tree` verified for `skills/git-signoff` and `conformance`.
4. Ephemeral review cleanup in Step 7b removes `integrate-git-signoff-48d1c2/`.
