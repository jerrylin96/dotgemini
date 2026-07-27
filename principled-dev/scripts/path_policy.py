#!/usr/bin/env python3
import json
import os
import shlex
import sys
from pathlib import Path

from principled_dev.config import roots
from principled_dev.state import StateStore


WRITE_TOOLS = {"developer__write", "developer__edit"}


def block(reason):
    return {"decision": "block", "reason": reason}


def _resolved_target(payload):
    raw = payload.get("tool_input", {}).get("path", "")
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(payload.get("working_dir") or os.getcwd()) / path
    return path.resolve(strict=False)


def _inside(path, root):
    try:
        path.relative_to(root)
        return path != root
    except ValueError:
        return False


def _integration_command(command, base):
    try:
        words = shlex.split(command)
    except ValueError:
        return True
    if len(words) >= 2 and words[:2] == ["git", "merge"]:
        return True
    if len(words) >= 2 and words[:2] == ["gh", "pr"] and "create" in words:
        return True
    if len(words) >= 3 and words[:2] == ["git", "push"]:
        refs = words[3:] if len(words) > 3 else ()
        protected = {base, f"refs/heads/{base}"}
        for ref in refs:
            ref = ref.removeprefix("+")
            destination = ref.split(":", 1)[-1]
            if destination in protected:
                return True
        return False
    return False


def _feature_root(working_dir=None):
    configured = os.environ.get("PRINCIPLED_DEV_FEATURE_WORKTREE", "").strip()
    if configured:
        return configured
    repository = os.environ.get("PRINCIPLED_DEV_REPOSITORY_ID", "").strip()
    feature = os.environ.get("PRINCIPLED_DEV_FEATURE_BRANCH", "").strip()
    _, state_root = roots()
    try:
        store = StateStore(state_root / "lifecycle.json")
        if repository and feature:
            metadata = store.get_metadata(repository, feature)
        else:
            metadata = store.find_metadata_for_path(working_dir or os.getcwd())
        return metadata.get("feature_worktree", "")
    except Exception:
        return ""


def decide(payload):
    tool = payload.get("tool_name", "")
    feature_root = _feature_root(payload.get("working_dir"))

    if tool in WRITE_TOOLS:
        if not feature_root:
            return block("principled-dev feature worktree is not configured")
        target = _resolved_target(payload)
        root = Path(feature_root).expanduser().resolve(strict=False)
        if target is None or not _inside(target, root):
            return block("repository edits must stay inside configured feature worktree")

    if tool == "developer__shell":
        if not feature_root:
            return block("principled-dev feature worktree is not configured")
        working_dir = Path(payload.get("working_dir") or os.getcwd()).resolve(strict=False)
        root = Path(feature_root).expanduser().resolve(strict=False)
        if working_dir != root and not _inside(working_dir, root):
            return block("advisory shell boundary requires feature-worktree working directory")
        command = payload.get("tool_input", {}).get("command", "")
        base = os.environ.get("PRINCIPLED_DEV_BASE_BRANCH", "main")
        if _integration_command(command, base):
            return block("advisory check: PR creation and integration mutation are human-owned")
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        decision = decide(payload)
        if decision:
            json.dump(decision, sys.stdout)
    except Exception as exc:
        # Hooks fail open at platform level; emit diagnostic without a false policy claim.
        print(f"principled-dev policy hook error: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
