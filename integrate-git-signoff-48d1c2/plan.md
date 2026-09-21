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

## Granular Task Breakdown (All Slices $\le$ 5 Files)

### Slice 1a: Subtree Script Modernization & Behavioral Tests
**Goal**: Update `scripts/sync_signoff_subtree.sh` and add behavioral test suite exercising adoption, repeat sync, squash lineage divergence fallback, and tree equality in an isolated git fixture.
**Files Touched (2)**: `scripts/sync_signoff_subtree.sh`, `scripts/tests/test_sync_subtree.py`.

- **RED Test Spec**:
  - In `scripts/tests/test_sync_subtree.py`, write `test_sync_subtree_script_behavior(tmp_path)`:
    1. Tests clean-worktree precondition check (exits 1 with `"error: working tree not clean"` when dirty).
    2. Tests first adoption (`git subtree add`) into an isolated fixture repo.
    3. Tests repeat sync (`git subtree merge`).
    4. Tests unrelated-history divergence fallback (when squash merge base fails across repo rename, re-adopts via `git subtree add`).
    5. Tests tree equality enforcement (`upstream_tree == local_tree`).
  - Expected Failure: `AssertionError` or returncode mismatch because `scripts/sync_signoff_subtree.sh` currently lacks the fallback logic and targets the old repo.
- **GREEN Implementation Target**:
  - Update `scripts/sync_signoff_subtree.sh`:
    - Set `SRC="https://github.com/jerrylin96/git-signoff"`.
    - Set prefixes list to `skills/git-signoff conformance`.
    - Add merge fallback: if `git subtree merge` fails, fall back to clean re-adoption via `git subtree add`.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_sync_subtree.py -k test_sync_subtree_script_behavior
  ```
- **Clean Worktree Checkpoint**:
  - Target commit: `git add scripts/sync_signoff_subtree.sh scripts/tests/test_sync_subtree.py && git commit -m "feat(sync): add subtree script fallback and behavioral tests"`
  - Verify clean status: `[ -z "$(git status --porcelain)" ]` before advancing to Slice 1b.

---

### Slice 1b: Mechanical Legacy Purge & Subtree Adoption
**Goal**: Purge legacy `skills/signoff` and `signoff_mcp`, execute `scripts/sync_signoff_subtree.sh` on clean worktree, and update Claude skill symlink.
**Files Touched (4)**: `skills/signoff` (purged), `signoff_mcp` (purged), `.claude/skills/git-signoff` (symlink), `conformance` (subtree).

- **RED Test Spec**:
  - In `scripts/tests/test_sync_subtree.py`, add `test_subtree_adoption_state()`:
    1. Asserts `skills/git-signoff/SKILL.md` and `skills/git-signoff/attest.py` exist on disk.
    2. Asserts `conformance/vectors/` exists on disk.
    3. Asserts `skills/signoff` and `signoff_mcp` do NOT exist in git tracked files (`git ls-files`).
    4. Asserts `.claude/skills/git-signoff` symlink resolves to `../../skills/git-signoff`.
  - Expected Failure: `AssertionError: skills/git-signoff/SKILL.md does not exist`.
- **GREEN Implementation Target**:
  - Purge legacy paths: `git rm -r skills/signoff signoff_mcp`
  - Commit purge: `git commit -m "chore: purge legacy signoff and signoff_mcp subtrees"`
  - Verify `[ -z "$(git status --porcelain)" ]`.
  - Run sync script: `bash scripts/sync_signoff_subtree.sh https://github.com/jerrylin96/git-signoff main`
  - Update symlink: `rm -f .claude/skills/signoff && ln -s ../../skills/git-signoff .claude/skills/git-signoff && git add .claude/skills/git-signoff`
  - Commit symlink: `git commit -m "chore: point .claude/skills/git-signoff symlink to skills/git-signoff"`
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_sync_subtree.py -k test_subtree_adoption_state
  ```
- **Clean Worktree Checkpoint**: Verify `git status --porcelain` is empty.

---

### Slice 2: Packaging, CI Workflow & Repo Configuration
**Goal**: Remove dead MCP entrypoints/dependencies from `pyproject.toml` and `pytest.ini`, and configure CI workflow action and permissions.
**Files Touched (4)**: `scripts/tests/test_repo_configuration.py`, `pyproject.toml`, `pytest.ini`, `.github/workflows/signoff.yml`.

- **RED Test Spec**:
  - In `scripts/tests/test_repo_configuration.py`, write `test_pyproject_and_workflow_schema()`:
    1. Asserts `signoff-mcp` is not in `pyproject.toml` under `[project.scripts]`.
    2. Asserts `signoff_mcp*` is not in `pyproject.toml` `packages.find include`.
    3. Asserts `mcp` is not in `pyproject.toml` `[project.optional-dependencies]`.
    4. Asserts `signoff_mcp/tests` is not in `pytest.ini` `testpaths`.
    5. Asserts `.github/workflows/signoff.yml` references `jerrylin96/git-signoff/verify@verify-v1.7`.
    6. Asserts `.github/workflows/signoff.yml` contains `permissions:` with `contents: read` and `pull-requests: read`.
  - Expected Failure: `AssertionError: 'signoff-mcp' found in pyproject.toml`.
- **GREEN Implementation Target**:
  - Edit `pyproject.toml` to remove `signoff-mcp`, `signoff_mcp*`, and `mcp = ["mcp"]`.
  - Edit `pytest.ini` to remove `signoff_mcp/tests`.
  - Edit `.github/workflows/signoff.yml` to set action `verify@verify-v1.7` and add the `permissions` block.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_repo_configuration.py
  ```
- **Clean Worktree Checkpoint**: Commit changes and verify `git status --porcelain` is clean.

---

### Slice 3a: Primary Documentation & Lifecycle Guides
**Goal**: Update slash command and skill references from `/signoff` to `/git-signoff` across top-level docs and make-feature guides.
**Files Touched (5)**: `scripts/tests/test_primary_docs.py`, `AGENTS.md`, `README.md`, `skills/make-feature/SKILL.md`, `skills/make-feature/resources/lifecycle-guide.md`.

- **RED Test Spec**:
  - In `scripts/tests/test_primary_docs.py`, write `test_primary_docs_reference_git_signoff()`:
    1. Asserts `AGENTS.md` maps `/git-signoff` to `skills/git-signoff/SKILL.md` and contains no `/signoff` table entry.
    2. Asserts `README.md` documents `/git-signoff` and contains no `/signoff` references.
    3. Asserts `skills/make-feature/SKILL.md` lines 254 & 273 reference `/git-signoff` and `../git-signoff/SKILL.md`.
    4. Asserts `skills/make-feature/resources/lifecycle-guide.md` links to `../../git-signoff/SKILL.md`.
  - Expected Failure: `AssertionError: '/signoff' found in AGENTS.md`.
- **GREEN Implementation Target**:
  - Update `AGENTS.md` (and verify symlinked `GEMINI.md`).
  - Update `README.md`.
  - Update `skills/make-feature/SKILL.md`.
  - Update `skills/make-feature/resources/lifecycle-guide.md`.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_primary_docs.py
  ```
- **Clean Worktree Checkpoint**: Commit changes and verify `git status --porcelain` is clean.

---

### Slice 3b: Dependent Skill References & Link Cleanliness
**Goal**: Update dependent skills (`catchmeup`, `math-proof-audit`) and verify zero dead markdown links or broken `@skill:signoff` references exist across the repository.
**Files Touched (3)**: `skills/catchmeup/SKILL.md`, `skills/math-proof-audit/SKILL.md`, `scripts/tests/test_skill_references.py`.

- **RED Test Spec**:
  - In `scripts/tests/test_skill_references.py`, add `test_dependent_skills_and_links()`:
    1. Asserts `skills/catchmeup/SKILL.md` links to `../git-signoff/SKILL.md`.
    2. Asserts `skills/math-proof-audit/SKILL.md` references `@skill:git-signoff` and `/git-signoff`.
    3. Recursively scans all tracked `*.md` files: asserts zero occurrences of `@skill:signoff` and zero markdown links referencing `skills/signoff/`.
  - Expected Failure: `AssertionError: '@skill:signoff' found in skills/math-proof-audit/SKILL.md`.
- **GREEN Implementation Target**:
  - Update `skills/catchmeup/SKILL.md` (line 34 link).
  - Update `skills/math-proof-audit/SKILL.md` (Phase 3 text and references).
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_skill_references.py -k "test_dependent_skills_and_links or test_all_skill_references_resolve"
  ```
- **Clean Worktree Checkpoint**: Commit changes and verify `git status --porcelain` is clean.

---

### Slice 4a: Test Port Helpers & Production Vectors
**Goal**: Port dynamic import loader, isolated repository helpers, conftest fixtures, and production attestation vector test.
**Files Touched (5)**: `scripts/tests/_attest_loader.py`, `scripts/tests/helpers.py`, `scripts/tests/conftest.py`, `scripts/tests/fixtures/production_attestation.txt`, `scripts/tests/test_production_vector.py`.

- **RED Test Spec**:
  - In `scripts/tests/test_production_vector.py`, write `test_production_vector_loading(tmp_path)`:
    1. Dynamically imports `skills/git-signoff/attest.py` via `_attest_loader.py`.
    2. Parses `scripts/tests/fixtures/production_attestation.txt`.
    3. Runs `check_head()` / `validate_single()` from `attest.py` against the production vector.
  - Expected Failure: `ModuleNotFoundError: No module named '_attest_loader'`.
- **GREEN Implementation Target**:
  - Write `scripts/tests/_attest_loader.py` using `importlib.util.spec_from_file_location` targeting `skills/git-signoff/attest.py`.
  - Port `scripts/tests/helpers.py` providing isolated `init_repo` and `commit_file` with explicit git credentials.
  - Port `scripts/tests/conftest.py` ensuring environment isolation.
  - Port `scripts/tests/fixtures/production_attestation.txt`.
  - Port `scripts/tests/test_production_vector.py`.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_production_vector.py
  ```
- **Clean Worktree Checkpoint**: Commit changes and verify `git status --porcelain` is clean.

---

### Slice 4b: Core Attestation & Adapter Tests
**Goal**: Port upstream unit tests for core mechanics (`attest.py`), transcript adapters, and learning modes.
**Files Touched (3)**: `scripts/tests/test_attest.py`, `scripts/tests/test_attest_adapters.py`, `scripts/tests/test_learning_modes.py`.

- **RED Test Spec**:
  - In `scripts/tests/test_attest.py`, specify behavioral assertion `test_prepare_and_commit_flow(tmp_path)`: executes `attest.py prepare` generating `.git/git-signoff/prepared.json`, executes `attest.py commit` asserting returncode 0 and verifying trailers on the HEAD commit.
  - In `scripts/tests/test_attest_adapters.py`, specify `test_antigravity_adapter(tmp_path)`: verifies transcript resolution when `ANTIGRAVITY_CONVERSATION_ID` is set.
  - In `scripts/tests/test_learning_modes.py`, specify `test_practice_session_separation(tmp_path)`: verifies practice mode session record blocks attestation commit.
  - Expected Failure: `AssertionError` if test files are empty or unimported.
- **GREEN Implementation Target**:
  - Port `test_attest.py` (core mechanics, exit codes 0/2/3/4/5/6/7, rollbacks).
  - Port `test_attest_adapters.py` (transcript adapters and worktree fallback).
  - Port `test_learning_modes.py` (`--explain` and `--practice` session handling).
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_attest.py scripts/tests/test_attest_adapters.py scripts/tests/test_learning_modes.py
  ```
- **Clean Worktree Checkpoint**: Commit changes and verify `git status --porcelain` is clean.

---

### Slice 4c: Notes Merge, Profiles & Contract Test Modernization
**Goal**: Port notes merge and profile tests, and update existing contract tests in `test_skill_references.py`.
**Files Touched (3)**: `scripts/tests/test_attest_notes_merge.py`, `scripts/tests/test_attest_profile.py`, `scripts/tests/test_skill_references.py`.

- **RED Test Spec**:
  - In `scripts/tests/test_skill_references.py`, update existing contract tests:
    1. `test_all_skills_have_correct_frontmatter_name`: asserts `skills/git-signoff/SKILL.md` frontmatter has `name: git-signoff`.
    2. `test_signoff_socratic_remediation_rule`: asserts Socratic remediation, evaluation, uncertainty handling, explain-diff references, and the **Worktree Target Mandate** (`worktree_path`) against `skills/git-signoff/SKILL.md`.
    3. `test_signoff_gsa_protocol_spec_and_trailers`: asserts GSA v1.0 trailers, `refs/notes/signoff`, and `cat_sort_uniq` across `skills/git-signoff/specs/gsa-core.md` and `skills/git-signoff/attest.py`.
    4. `test_signoff_phase3c_interview_contract`: targets `skills/git-signoff/` paths (`HARNESSES.md`, `profiles/software-general.md`, `profiles/domain-science.md`, `SKILL.md`).
  - Expected Failure: `AssertionError: Directory skills/signoff does not exist` (pointing to old path).
- **GREEN Implementation Target**:
  - Port `scripts/tests/test_attest_notes_merge.py` (`cat_sort_uniq` tracking ref merge).
  - Port `scripts/tests/test_attest_profile.py` (profile resolution, science signals).
  - Update `scripts/tests/test_skill_references.py` contract tests to assert against `skills/git-signoff` and `attest.py`.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_attest_notes_merge.py scripts/tests/test_attest_profile.py scripts/tests/test_skill_references.py
  ```
- **Clean Worktree Checkpoint**: Commit changes and verify `git status --porcelain` is clean.

---

## Acceptance Verification
1. `python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest` passes 100% across all tests.
2. `python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 ruff check .` passes with zero violations.
3. `upstream_tree == local_tree` verified for `skills/git-signoff` and `conformance`.
4. Ephemeral review cleanup in Step 7b removes `integrate-git-signoff-48d1c2/`.
