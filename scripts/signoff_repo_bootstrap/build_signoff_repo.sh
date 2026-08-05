#!/usr/bin/env bash
# Deterministically build the standalone jerrylin96/signoff repository from
# dotgemini history (GSA Phase 4 extraction). Producing identical commit SHAs
# on every run is a design requirement: dotgemini's subtree-squash metadata
# references these SHAs, so a rebuild (e.g. recovery from a fresh clone) must
# reproduce them byte-for-byte before pushing.
#
# Usage: build_signoff_repo.sh <output-dir> [dotgemini-clone-url-or-path]
# Requires: git-filter-repo (pip install git-filter-repo), python3.
#
# After a successful build, publish with:
#   cd <output-dir>
#   git remote add origin https://github.com/jerrylin96/signoff
#   git push -u origin main
set -euo pipefail

OUT=${1:?usage: build_signoff_repo.sh <output-dir> [dotgemini-url-or-path]}
SRC=${2:-https://github.com/jerrylin96/dotgemini}
BOOTSTRAP_DIR=$(cd "$(dirname "$0")" && pwd)

# Pinned extraction point: dotgemini main at the Phase 3c merge (PR #58).
DOTGEMINI_MAIN_SHA=9f21b6035e0a6fe00aa0d55b6fc7bedb13905dfd

# Fixed identity + timestamps make the repackaging commit reproducible.
export GIT_AUTHOR_NAME="Jerry Lin"
export GIT_AUTHOR_EMAIL="22736732+jerrylin96@users.noreply.github.com"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
export GIT_AUTHOR_DATE="2026-08-05T12:00:00Z"
export GIT_COMMITTER_DATE="2026-08-05T12:00:00Z"

[ -e "$OUT" ] && { echo "error: $OUT already exists" >&2; exit 1; }

git clone --no-local --single-branch --branch main "$SRC" "$OUT"
cd "$OUT"
if [ "$(git rev-parse HEAD)" != "$DOTGEMINI_MAIN_SHA" ]; then
    git fetch origin "$DOTGEMINI_MAIN_SHA"
    git checkout -B main "$DOTGEMINI_MAIN_SHA"
fi

git filter-repo --force \
    --path skills/signoff \
    --path signoff_mcp \
    --path scripts/tests/test_skill_references.py

# Overlay the new-repo root files (manifests, packaging, docs, trimmed tests).
cp -R "$BOOTSTRAP_DIR/overlay/." .

# Apply skill-content edits (self-containment link fix, live install channels,
# phase-gate status updates). Fails loudly if context drifted.
python3 "$BOOTSTRAP_DIR/apply_skill_edits.py" .

git add -A
git commit -m "Repackage as standalone signoff plugin marketplace (GSA Phase 4)

Extracted from jerrylin96/dotgemini@${DOTGEMINI_MAIN_SHA:0:7} via git
filter-repo (skills/signoff, signoff_mcp, and the skill contract test, full
history). Adds the Claude Code plugin marketplace layout (.claude-plugin/
marketplace.json + plugin.json with the repo root as the plugin), signoff-mcp
packaging (pyproject.toml), plugin-manifest contract tests, a trimmed
skill-references contract suite with a new self-containment test (Phase 3a),
MIT license, and README. Skill edits: make-feature link reduced to a graceful
plain-text reference, HARNESSES.md install channels point at the live repo,
gsa-core.md ticks Phase 3a and records Phase 4 shipped-pending-verification.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QhWsf2k3GiJRFRqEWA3xcF"

echo
echo "Built $(git rev-parse HEAD) at $OUT"
