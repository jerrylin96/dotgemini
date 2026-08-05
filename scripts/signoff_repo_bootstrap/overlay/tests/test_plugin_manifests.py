"""Contract tests for the Claude Code plugin marketplace layout (GSA Phase 4).

The repo root is simultaneously the marketplace root and the plugin root:
.claude-plugin/marketplace.json lists a single plugin sourced from "./", and
.claude-plugin/plugin.json is that plugin's manifest. Skills are discovered
at skills/<name>/SKILL.md relative to the plugin root.
"""

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load(relpath):
    with open(os.path.join(ROOT, relpath), "r", encoding="utf-8") as f:
        return json.load(f)


def test_marketplace_manifest_contract():
    mp = _load(".claude-plugin/marketplace.json")
    assert mp["name"] == "signoff"
    assert mp["owner"]["name"], "marketplace owner.name required"
    assert isinstance(mp["plugins"], list) and len(mp["plugins"]) == 1
    plugin = mp["plugins"][0]
    assert plugin["name"] == "signoff"
    assert plugin["source"] == "./", "repo root must be the plugin root"
    assert plugin["description"].strip()


def test_plugin_manifest_contract():
    pj = _load(".claude-plugin/plugin.json")
    assert pj["name"] == "signoff"
    assert pj["description"].strip()
    assert re.match(r"^\d+\.\d+\.\d+$", pj["version"])


def test_versions_are_synchronized():
    """plugin.json, marketplace plugin entry, and signoff_mcp.__version__ agree."""
    pj = _load(".claude-plugin/plugin.json")
    mp = _load(".claude-plugin/marketplace.json")
    sys.path.insert(0, ROOT)
    try:
        import signoff_mcp
    finally:
        sys.path.pop(0)
    assert pj["version"] == mp["plugins"][0]["version"] == signoff_mcp.__version__


def test_plugin_ships_the_signoff_skill():
    skill_md = os.path.join(ROOT, "skills", "signoff", "SKILL.md")
    assert os.path.exists(skill_md), "plugin skill skills/signoff/SKILL.md missing"
    with open(skill_md, "r", encoding="utf-8") as f:
        head = f.read(2048)
    assert head.startswith("---"), "SKILL.md must open with YAML frontmatter"
    assert re.search(r"^name:\s*signoff\s*$", head, re.MULTILINE), (
        "SKILL.md frontmatter name must be 'signoff'"
    )
