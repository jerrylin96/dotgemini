"""Wiring tests for harvested pstack practices across streamlined AGENTS.md and skills."""

from pathlib import Path
import re

WORKTREE_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = WORKTREE_ROOT / rel_path
    assert path.exists(), f"Expected file does not exist: {rel_path}"
    return path.read_text(encoding="utf-8")


def _extract_frontmatter_field(content: str, field: str) -> str:
    """Extract a YAML frontmatter scalar or folded/literal block without PyYAML."""
    lines = content.splitlines()
    assert lines and lines[0] == "---", "Missing opening frontmatter delimiter"
    fm_lines = []
    for line in lines[1:]:
        if line == "---":
            break
        fm_lines.append(line)

    pattern = re.compile(rf"^{re.escape(field)}:\s*(.*)$")
    for idx, line in enumerate(fm_lines):
        match = pattern.match(line)
        if not match:
            continue
        raw = match.group(1).strip()
        if raw in (">", ">-", "|", "|-"):
            collected = []
            for cont in fm_lines[idx + 1 :]:
                if cont and not cont[0].isspace():
                    break
                collected.append(cont.strip())
            return " ".join(part for part in collected if part)
        if (raw.startswith('"') and raw.endswith('"')) or (
            raw.startswith("'") and raw.endswith("'")
        ):
            return raw[1:-1].strip()
        return raw
    raise AssertionError(f"Frontmatter missing field: {field}")


def _section_between(text: str, start_marker: str, end_marker: str | None = None) -> str:
    start_idx = text.find(start_marker)
    assert start_idx != -1, f"Missing marker: {start_marker!r}"
    sub = text[start_idx:]
    if end_marker is not None:
        end_idx = sub.find(end_marker, len(start_marker))
        if end_idx != -1:
            sub = sub[:end_idx]
    return sub


def test_benchmark_checklist_frontmatter_and_rules():
    """benchmark-checklist skill has imperative scoped trigger and 7 questions."""
    content = _read("skills/benchmark-checklist/SKILL.md")
    desc = _extract_frontmatter_field(content, "description")
    desc_lower = desc.lower()

    assert desc.startswith("CRITICAL RULE:")
    assert "changeset" in desc_lower
    for kw in ("benchmark", "latency", "throughput", "speedup", "profiling", "regression"):
        assert kw in desc_lower, f"Description missing trigger keyword: {kw}"

    body_lower = content.lower()
    for question in (
        "why not double?",
        "was it tuned?",
        "did it break limits?",
        "did it error?",
        "does it reproduce?",
        "does it matter?",
        "did it even happen?",
    ):
        assert question in body_lower, f"Missing checklist question: {question}"

    assert "inconclusive" in body_lower
    assert "methodology" in body_lower and "re-benchmark" in body_lower


def test_agents_md_benchmark_state_and_ponytail_wiring():
    """AGENTS.md enforces benchmark-checklist tripwire, state transitions, downstream trace, and encode lessons."""
    agents = _read("AGENTS.md")

    ponytail_rules = _section_between(agents, "### Key Rules", "## 2. Caveman")
    rules_lower = ponytail_rules.lower()
    assert "Downstream Consumer Trace" in ponytail_rules
    assert "indirect" in rules_lower and "grep" in rules_lower
    assert "execution" in rules_lower
    assert "Encode lessons in structure" in ponytail_rules
    assert "linter" in rules_lower and "test" in rules_lower

    tiers = _section_between(agents, "### Complexity Tiers", "### Core Operating Invariants")
    assert "State transitions:" in tiers
    for term in ("background", "retry", "cancellation", "illegal", "timeout", "error"):
        assert term in tiers.lower()

    invariants = _section_between(agents, "### Core Operating Invariants", "## 4. On-Demand Skills")
    assert "benchmark-checklist" in invariants
    assert "changeset" in invariants.lower()

    skills_section = _section_between(agents, "## 4. On-Demand Skills", "## 5.")
    assert "[benchmark-checklist/SKILL.md](skills/benchmark-checklist/SKILL.md)" in skills_section


def test_adversarial_review_pstack_gates():
    """adversarial-review includes Downstream Consumer Trace, @skill:benchmark-checklist, and --unslop."""
    adv = _read("skills/adversarial-review/SKILL.md")
    checklist = _section_between(adv, "## Step 4: Adversarial Audit Checklist", "## Step 5:")
    lower = checklist.lower()

    assert "Downstream Consumer Trace" in checklist
    assert "beyond" in lower and "grep" in lower
    assert "unproven" in lower and "execution" in lower

    assert "@skill:benchmark-checklist" in checklist
    assert "limiter" in lower and "tuned" in lower and "ballpark" in lower

    assert "[prose-editor](../prose-editor/SKILL.md)" in checklist
    assert "--unslop" in checklist and "inline" in lower
    assert "@skill:prose-editor" not in checklist


def test_unslop_tier_precedence_in_prose_editor():
    """prose-editor has --unslop tier and surface precedence with caveman."""
    pe = _read("skills/prose-editor/SKILL.md")
    triggers = _section_between(pe, "## Command Triggers", "## Core Principles")
    principles = _section_between(pe, "## Core Principles", "## Editing Tiers")
    tiers = _section_between(pe, "## Editing Tiers", "## Suggestion Card Schema")

    assert "--unslop" in triggers
    assert "--unslop" in tiers

    principles_lower = principles.lower()
    assert "unslop" in principles_lower and "caveman" in principles_lower
    assert "chat" in principles_lower and ("external" in principles_lower or "document" in principles_lower)

    tiers_lower = tiers.lower()
    for canonical_token in ("ai vocabulary", "em dash", "abstract metaphor nouns", "over-compression"):
        assert canonical_token in tiers_lower, f"Missing canonical unslop token: {canonical_token}"
