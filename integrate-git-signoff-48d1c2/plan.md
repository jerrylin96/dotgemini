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
**Goal**: Update `scripts/sync_signoff_subtree.sh` to track upstream `jerrylin96/git-signoff`, restrict squash fallback strictly to unrelated histories, and add behavioral tests in an isolated git fixture.
**Files Touched (2)**: `scripts/sync_signoff_subtree.sh`, `scripts/tests/test_sync_subtree.py`.

- **RED Test Spec**:
  - In `scripts/tests/test_sync_subtree.py`, write `test_sync_subtree_script_behavior(tmp_path)`:
    1. Tests clean-worktree precondition check (exits 1 with `"error: working tree not clean"` when dirty).
    2. Tests first adoption (`git subtree add`) into an isolated fixture repo.
    3. Tests repeat sync (`git subtree merge`).
    4. Tests strictly-scoped unrelated-history divergence fallback: captures `refusing to merge unrelated histories` (or missing merge-base across repo rename) and re-adopts via `git subtree add`.
    5. Tests that other non-lineage errors (e.g. merge conflicts, corrupt tree) fail loudly without re-adoption.
    6. Tests tree equality enforcement (`upstream_tree == local_tree`).
  - Expected Failure: `AssertionError: expected unrelated-history fallback` because `scripts/sync_signoff_subtree.sh` currently targets the old repo and lacks the scoped fallback.
- **GREEN Implementation Target**:
  - Update `scripts/sync_signoff_subtree.sh`:
    - Set `SRC="https://github.com/jerrylin96/git-signoff"`.
    - Set prefixes list to `skills/git-signoff conformance`.
    - Restrict merge fallback: catch output from `git subtree merge`; only if the error explicitly indicates unrelated histories (e.g. `refusing to merge unrelated histories` or no common ancestor), fall back to clean re-adoption via `git subtree add`. All other merge failures halt with exit code 1.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_sync_subtree.py -k test_sync_subtree_script_behavior
  ```
- **Clean Worktree Checkpoint**:
  - Target commit: `git add scripts/sync_signoff_subtree.sh scripts/tests/test_sync_subtree.py && git commit -m "feat(sync): add scoped subtree fallback and behavioral tests"`
  - Verify clean status: `[ -z "$(git status --porcelain)" ]` before advancing to Slice 1b.

---

### Slice 1b: Mechanical Legacy Purge & Subtree Adoption
**Goal**: Purge legacy `skills/signoff` and `signoff_mcp`, execute `scripts/sync_signoff_subtree.sh` on clean worktree, and update Claude skill symlink with staged deletion.
**Files Touched (4)**: `skills/signoff` (purged), `signoff_mcp` (purged), `.claude/skills/` (symlink updated), `conformance` (subtree).

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
  - Update symlink with staged deletion:
    ```bash
    git rm .claude/skills/signoff
    ln -s ../../skills/git-signoff .claude/skills/git-signoff
    git add .claude/skills/git-signoff
    git commit -m "chore: point .claude/skills/git-signoff symlink to skills/git-signoff"
    ```
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
**Goal**: Update dependent skills (`catchmeup`, `math-proof-audit`) and verify zero dead markdown links or broken `@skill:signoff` references exist in active documentation.
**Files Touched (3)**: `skills/catchmeup/SKILL.md`, `skills/math-proof-audit/SKILL.md`, `scripts/tests/test_skill_references.py`.

- **RED Test Spec**:
  - In `scripts/tests/test_skill_references.py`, add `test_dependent_skills_and_links()`:
    1. Asserts `skills/catchmeup/SKILL.md` links to `../git-signoff/SKILL.md`.
    2. Asserts `skills/math-proof-audit/SKILL.md` references `@skill:git-signoff` and `/git-signoff`.
    3. Recursively scans all active markdown files in `skills/` (explicitly excluding the ephemeral migration directory `integrate-git-signoff-48d1c2/` which mentions historical terms): asserts zero occurrences of `@skill:signoff` and zero markdown links referencing `skills/signoff/`. Full repository-wide zero-match scan runs post-cleanup.
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
  - Write a collected integration assertion in `scripts/tests/test_production_vector.py`:
    1. Defines `test_attest_loader_wires_attest_module()` asserting that `_attest_loader` dynamically loads `attest.py` and exposes public callable `parse_trailers`.
    2. Defines `test_parse_trailers_production_vector()` asserting that `core.parse_trailers()` parses `fixtures/production_attestation.txt` matching expected trailers.
    3. Defines `test_build_message_roundtrips_production_vector()` asserting that `core.build_message()` roundtrips the production payload.
  - Expected Failure: Initial run fails with `AssertionError: _attest_loader failed to resolve attest.py` (before loader implementation).
- **GREEN Implementation Target**:
  - Write `scripts/tests/_attest_loader.py` using `importlib.util.spec_from_file_location` targeting `skills/git-signoff/attest.py`.
  - Port `scripts/tests/helpers.py` providing isolated `init_repo` and `commit_file` with explicit git credentials.
  - Port `scripts/tests/conftest.py` ensuring environment isolation.
  - Port `scripts/tests/fixtures/production_attestation.txt`.
  - Port `scripts/tests/test_production_vector.py` using `core.parse_trailers()` and `core.build_message()`.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_production_vector.py
  ```
- **Clean Worktree Checkpoint**: Commit changes and verify `git status --porcelain` is clean.

---

### Slice 4b: Core Attestation & Adapter Regression Tests
**Goal**: Port upstream regression suites for core mechanics (`attest.py`), transcript adapters, and learning modes without inventing synthetic failures.
**Files Touched (3)**: `scripts/tests/test_attest.py`, `scripts/tests/test_attest_adapters.py`, `scripts/tests/test_learning_modes.py`.

- **Regression Port Specification**:
  - Port upstream regression suites directly from `jerrylin96/git-signoff`:
    - `scripts/tests/test_attest.py`: Core attestation mechanics (prepare, marker check, commit, rollback, exit codes 0/2/3/4/5/6/7).
    - `scripts/tests/test_attest_adapters.py`: Transcript adapters (Antigravity, Claude Code, Codex, generic) and linked worktree fallback.
    - `scripts/tests/test_learning_modes.py`: `--explain` walkthrough and `--practice` local session record isolation.
  - All tests execute in isolated temporary repositories (`tmp_path`) with clean environment variables.
- **GREEN Implementation Target**:
  - Port `test_attest.py`.
  - Port `test_attest_adapters.py`.
  - Port `test_learning_modes.py`.
- **Verify Command**:
  ```bash
  python3 ~/.gemini/scripts/run_in_env.py /Users/jerrylin/.gemini/tmp/worktrees/integrate-git-signoff-48d1c2 pytest scripts/tests/test_attest.py scripts/tests/test_attest_adapters.py scripts/tests/test_learning_modes.py
  ```
- **Clean Worktree Checkpoint**: Commit changes and verify `git status --porcelain` is clean.

---

### Slice 4c: Notes Merge, Profiles & Contract Test Modernization
**Goal**: Port notes merge and profile tests, and modernize contract assertions in `test_skill_references.py`.
**Files Touched (3)**: `scripts/tests/test_attest_notes_merge.py`, `scripts/tests/test_attest_profile.py`, `scripts/tests/test_skill_references.py`.

- **RED Test Spec**:
  - In `scripts/tests/test_skill_references.py`, update existing contract tests:
    1. `test_all_skills_have_correct_frontmatter_name`: asserts `skills/git-signoff/SKILL.md` frontmatter has `name: git-signoff`.
    2. `test_signoff_socratic_remediation_rule`: asserts Socratic remediation, evaluation, uncertainty handling, explain-diff references, and the **Worktree Target Mandate** (`worktree_path`) against `skills/git-signoff/SKILL.md`.
    3. `test_signoff_gsa_protocol_spec_and_trailers`: asserts GSA v1.0 trailers, `refs/notes/signoff`, and `cat_sort_uniq` across `skills/git-signoff/specs/gsa-core.md` and `skills/git-signoff/attest.py`.
    4. `test_signoff_phase3c_interview_contract`: targets `skills/git-signoff/` paths (`HARNESSES.md`, `profiles/software-general.md`, `profiles/domain-science.md`, `SKILL.md`).
  - Expected Failure: `AssertionError: Directory skills/signoff does not exist` (prior to updating references to `skills/git-signoff`).
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
