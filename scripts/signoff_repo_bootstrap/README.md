# signoff repo bootstrap (GSA Phase 4)

One-time, deterministic extraction of the standalone
[jerrylin96/signoff](https://github.com/jerrylin96/signoff) repository from
dotgemini history. Kept in-tree as the recovery artifact until the standalone
repo is pushed and verified; after that, the standalone repo is authoritative
and this directory is historical (safe to delete).

- `build_signoff_repo.sh <out-dir> [dotgemini-url-or-path]` — clones dotgemini
  at the pinned Phase 3c merge SHA, runs `git filter-repo` over
  `skills/signoff/`, `signoff_mcp/`, and the skill contract test, copies
  `overlay/` (plugin marketplace manifests, packaging, docs, trimmed tests)
  onto the root, applies `apply_skill_edits.py`, and commits with pinned
  identity/timestamps. Every run reproduces the same HEAD SHA
  (`f9a655d6726b56a51c40e159c6e035eba338d592`), so the repo can be rebuilt and
  pushed from any clone. Requires `pip install git-filter-repo`.
- To publish (once `github.com/jerrylin96/signoff` exists, empty):
  ```bash
  bash scripts/signoff_repo_bootstrap/build_signoff_repo.sh /tmp/signoff-repo
  cd /tmp/signoff-repo
  git remote add origin https://github.com/jerrylin96/signoff
  git push -u origin main
  ```
- Ongoing consumption after bootstrap: `scripts/sync_signoff_subtree.sh`.
