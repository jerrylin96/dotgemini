#!/usr/bin/env python3
"""Apply Phase 4 skill-content edits to an extracted signoff repo tree.

Run from the extracted repo root. Each replacement must match exactly once.
"""
import sys

EDITS = {
    "skills/signoff/SKILL.md": [
        (
            "matching Step 8 in [make-feature](../make-feature/SKILL.md).",
            "matching Step 8 of the make-feature skill (in harnesses that ship it).",
        ),
    ],
    "skills/signoff/HARNESSES.md": [
        (
            "Nothing to install: this repo is the Antigravity global config; the skill is\nindexed in `AGENTS.md` and maps to `/signoff`.",
            "In the [dotgemini](https://github.com/jerrylin96/dotgemini) Antigravity global\nconfig this skill is indexed natively in `AGENTS.md` and maps to `/signoff`;\non other Antigravity setups, copy the folder per the Portability Rules.",
        ),
        (
            "Claude Code does not read this repo's root `skills/` layout. Install signoff as\na **user-level skill** so it follows you across sessions and repositories:",
            "Preferred: install the signoff **plugin** (see \"Distribution to end users\"\nbelow) so `/signoff` follows your account everywhere. The proven fallback is\ninstalling a **user-level skill** by zip upload:",
        ),
        (
            "- **All projects, any surface**: claude.ai Directory → Plugins → \"Add from a\n  repository\" syncs a plugin marketplace from a git URL at the account level\n  (planned primary channel once the dedicated signoff repo ships\n  `.claude-plugin/marketplace.json`; account-scoped like account skills —\n  verify cloud-session sync during dogfood). Machine-local plugin installs\n  (`~/.claude/settings.json`) do not transfer to cloud sessions.",
            "- **All projects, any surface (primary)**: claude.ai Directory → Plugins →\n  \"Add from a repository\" → `https://github.com/jerrylin96/signoff`, then\n  install the `signoff` plugin. The repo root ships\n  `.claude-plugin/marketplace.json` + `plugin.json`, so the repo itself is the\n  marketplace; installs are account-scoped like account skills (cloud-session\n  sync verification in progress). CLI/desktop equivalent:\n  `/plugin marketplace add jerrylin96/signoff` then\n  `/plugin install signoff@signoff`. Machine-local plugin installs\n  (`~/.claude/settings.json`) do not transfer to cloud sessions.",
        ),
        (
            "pip install \"dotgemini[mcp] @ git+https://github.com/jerrylin96/dotgemini\"",
            "pip install \"signoff-mcp @ git+https://github.com/jerrylin96/signoff\"",
        ),
    ],
    "skills/signoff/specs/gsa-core.md": [
        (
            "- [ ] Phase 3a (Portability): per-harness install & portability guide (`skills/signoff/HARNESSES.md`); skill folder self-contained for copy-paste installation as a user-level Claude Code skill.",
            "- [x] Phase 3a (Portability): per-harness install & portability guide (`skills/signoff/HARNESSES.md`); skill folder self-contained for copy-paste installation as a user-level Claude Code skill. Shipped 2026-08-05: external skill links reduced to graceful-degradation references; enforced by `scripts/tests/test_skill_references.py::test_skill_folder_is_self_contained` in the standalone repo.",
        ),
        (
            "self-contained folder copy for other harnesses per `skills/signoff/HARNESSES.md`.",
            "self-contained folder copy for other harnesses per `skills/signoff/HARNESSES.md`. **Status 2026-08-05:** shipped pending verification — dedicated repo `jerrylin96/signoff` carries full `git filter-repo` history plus marketplace/plugin manifests at root; dotgemini consumes it via two `git subtree --squash` prefixes (`scripts/sync_signoff_subtree.sh`); GitHub Pages, PyPI publish, and MCP bundling inside the plugin remain deferred; tick this box after the claude.ai Directory install loads `/signoff` in a fresh cloud session (Directory-sync verification).",
        ),
    ],
}


def main(root="."):
    failures = []
    for relpath, pairs in EDITS.items():
        path = f"{root}/{relpath}"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for old, new in pairs:
            n = content.count(old)
            if n != 1:
                failures.append(f"{relpath}: expected exactly 1 match, found {n} for: {old[:60]!r}...")
                continue
            content = content.replace(old, new)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        sys.exit(1)
    print("skill edits applied")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
