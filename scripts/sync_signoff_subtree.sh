#!/usr/bin/env bash
# Sync the git-signoff skill and conformance from the standalone repo.
#
# jerrylin96/git-signoff is the authoritative home of skills/git-signoff/
# and conformance/; dotagent consumes both as git-subtree squash prefixes so the
# committed .claude/skills/git-signoff symlink, pytest testpaths, and the skill
# contract tests keep working on unchanged real paths.
#
# The split is computed locally from the fetched branch, so the git-signoff repo
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

SRC=${1:-https://github.com/jerrylin96/git-signoff}
REF=${2:-main}

[ -z "$(git status --porcelain)" ] || { echo "error: working tree not clean" >&2; exit 1; }

git fetch "$SRC" "$REF"
FETCHED=$(git rev-parse FETCH_HEAD)
echo "Syncing from $SRC @ ${FETCHED}"

SPLIT_WT=$(mktemp -d)/split-wt
git worktree add --detach -q "$SPLIT_WT" "$FETCHED"
trap 'git worktree remove --force "$SPLIT_WT" >/dev/null 2>&1 || true' EXIT

for prefix in skills/git-signoff conformance; do
    split=$(git -C "$SPLIT_WT" subtree split --prefix="$prefix" HEAD)
    # Tracked-content check: ignored debris (e.g. __pycache__) must not make
    # a removed prefix look adopted.
    if [ -n "$(git ls-files "$prefix")" ]; then
        merge_output=""
        if ! merge_output=$(git subtree merge --prefix="$prefix" --squash "$split" \
            -m "Sync $prefix from git-signoff@${FETCHED:0:7}" 2>&1); then
            if echo "$merge_output" | grep -E -q "(refusing to merge unrelated histories|no common ancestor)"; then
                echo "Notice: squash merge failed with unrelated histories; re-adopting $prefix"
                git rm -r --ignore-unmatch "$prefix" >/dev/null 2>&1 || true
                if ! git diff --cached --quiet -- "$prefix"; then
                    git commit -m "chore: reset $prefix for subtree re-adoption" -- "$prefix"
                fi
                git subtree add --prefix="$prefix" --squash "$split" \
                    -m "Adopt $prefix as subtree from git-signoff@${FETCHED:0:7}"
            else
                echo "$merge_output" >&2
                echo "error: subtree merge failed for $prefix" >&2
                exit 1
            fi
        else
            echo "$merge_output"
        fi
    else
        git subtree add --prefix="$prefix" --squash "$split" \
            -m "Adopt $prefix as subtree from git-signoff@${FETCHED:0:7}"
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
        echo "Vendored copies accept changes only via the git-signoff repo; reconcile there and re-sync." >&2
        exit 1
    fi
done

echo "Done. Run pytest before pushing."
