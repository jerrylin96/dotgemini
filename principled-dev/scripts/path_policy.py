#!/usr/bin/env python3
import json
import os
import shlex
import sys
from pathlib import Path

from principled_dev.config import roots
from principled_dev.state import StateStore


WRITE_TOOLS = {"developer__write", "developer__edit"}
_LIFECYCLE_SCRIPT = Path(__file__).resolve().with_name("principled_dev.py")


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
            if "*" in ref or destination in protected:
                return True
        return False
    return False


def _bootstrap_command(command, working_dir):
    if any(char in command for char in "\n\r;&|<>`$(){}!*?[]~#"):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if len(words) < 5 or words[0] != "python3":
        return False
    script = Path(words[1]).expanduser()
    if not script.is_absolute():
        script = working_dir / script
    if script.resolve(strict=False) != _LIFECYCLE_SCRIPT:
        return False
    if words[2] != "--repo":
        return False
    repository = Path(words[3]).expanduser()
    if not repository.is_absolute():
        repository = working_dir / repository
    if repository.resolve(strict=False) != working_dir:
        return False

    if words[4] == "feature":
        return (
            len(words) == 8
            and words[5].startswith("agent/")
            and len(words[5]) > len("agent/")
            and words[6] == "--base"
            and bool(words[7])
        )

    if len(words) < 8 or words[4] != "--feature":
        return False
    if not words[5].startswith("agent/") or len(words[5]) == len("agent/"):
        return False
    if words[6] == "approve":
        return len(words) == 8 and words[7] in {"spec", "plan"}
    if len(words) != 9 or words[6] != "record-artifact" or words[7] not in {"spec", "plan"}:
        return False
    artifact = Path(words[8]).expanduser()
    if not artifact.is_absolute():
        artifact = working_dir / artifact
    _, state_root = roots()
    return _inside(artifact.resolve(strict=False), (state_root / "artifacts").resolve(strict=False))


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
        target = _resolved_target(payload)
        if not feature_root:
            _, state_root = roots()
            artifact_root = (state_root / "artifacts").resolve(strict=False)
            if target is not None and _inside(target, artifact_root):
                return None
            return block("principled-dev feature worktree is not configured")
        root = Path(feature_root).expanduser().resolve(strict=False)
        if target is None or not _inside(target, root):
            return block("repository edits must stay inside configured feature worktree")

    if tool == "developer__shell":
        working_dir = Path(payload.get("working_dir") or os.getcwd()).resolve(strict=False)
        command = payload.get("tool_input", {}).get("command", "")
        if not feature_root:
            if _bootstrap_command(command, working_dir):
                return None
            return block("principled-dev feature worktree is not configured")
        root = Path(feature_root).expanduser().resolve(strict=False)
        if working_dir != root and not _inside(working_dir, root):
            return block("advisory shell boundary requires feature-worktree working directory")
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
