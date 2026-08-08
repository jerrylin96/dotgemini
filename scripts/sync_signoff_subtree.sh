#!/usr/bin/env bash
# Sync the signoff skill + MCP server from the standalone repo (GSA Phase 4).
#
# jerrylin96/signoff is the authoritative home of skills/signoff/ and
# signoff_mcp/; dotgemini consumes both as git-subtree squash prefixes so the
# committed .claude/skills/signoff symlink, pytest testpaths, and the skill
# contract tests keep working on unchanged real paths.
#
# The split is computed locally from the fetched branch, so the signoff repo
# never needs to publish split branches. Splits are deterministic: re-running
# against the same upstream history regenerates the same split SHAs, which is
# what lets `git subtree merge` find the previous squash point recorded in
# the last sync commit.
#
# The split runs inside a temporary detached worktree of the fetched commit
# because `git subtree split` insists the prefix exists in the working tree
# it runs from — which is false here during first adoption (and irrelevant:
# the split reads the fetched commit, not the checkout). The worktree shares
# the object store, so the split commits are immediately usable.
#
# Usage: sync_signoff_subtree.sh [url-or-path] [ref]
set -euo pipefail

SRC=${1:-https://github.com/jerrylin96/signoff}
REF=${2:-main}

[ -z "$(git status --porcelain)" ] || { echo "error: working tree not clean" >&2; exit 1; }

git fetch "$SRC" "$REF"
FETCHED=$(git rev-parse FETCH_HEAD)
echo "Syncing from $SRC @ ${FETCHED}"

SPLIT_WT=$(mktemp -d)/split-wt
git worktree add --detach -q "$SPLIT_WT" "$FETCHED"
trap 'git worktree remove --force "$SPLIT_WT" >/dev/null 2>&1 || true' EXIT

for prefix in skills/signoff signoff_mcp conformance; do
    split=$(git -C "$SPLIT_WT" subtree split --prefix="$prefix" HEAD)
    # Tracked-content check: ignored debris (e.g. __pycache__) must not make
    # a removed prefix look adopted.
    if [ -n "$(git ls-files "$prefix")" ]; then
        git subtree merge --prefix="$prefix" --squash "$split" \
            -m "Sync $prefix from signoff@${FETCHED:0:7}"
    else
        git subtree add --prefix="$prefix" --squash "$split" \
            -m "Adopt $prefix as subtree from signoff@${FETCHED:0:7}"
    fi

    # Drift guard: a squash merge succeeds even when local-only edits have
    # diverged this prefix from upstream, and nothing else ever checks. Fail
    # loudly instead of leaving the vendored copy silently out of sync.
    upstream_tree=$(git rev-parse "${FETCHED}:${prefix}")
    local_tree=$(git rev-parse "HEAD:${prefix}")
    if [ "$upstream_tree" != "$local_tree" ]; then
        echo "error: $prefix diverges from upstream after sync" >&2
        echo "  local  ${local_tree}" >&2
        echo "  remote ${upstream_tree}" >&2
        echo "Vendored copies accept changes only via the signoff repo; reconcile there and re-sync." >&2
        exit 1
    fi
done

echo "Done. Run pytest before pushing."
