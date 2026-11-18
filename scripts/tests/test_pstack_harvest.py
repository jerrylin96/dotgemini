"""Novel wiring tests for harvested pstack practices (zero-dormancy gates)."""

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
    """Slice 1: benchmark-checklist skill has imperative scoped trigger and 7 questions."""
    content = _read("skills/benchmark-checklist/SKILL.md")
    desc = _extract_frontmatter_field(content, "description")
    desc_lower = desc.lower()

    assert desc.startswith("CRITICAL RULE:"), (
        "benchmark-checklist description must begin with 'CRITICAL RULE:'"
    )
    assert "changeset" in desc_lower, "Description must scope trigger to changeset claims"
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

    assert "inconclusive" in body_lower, "Must specify inconclusive verdict rule"
    assert "methodology" in body_lower and "re-benchmark" in body_lower, (
        "Must cover user-supplied methodology path without redundant re-benchmarking"
    )


def test_agents_md_benchmark_wiring():
    """Slice 1: AGENTS.md enforces benchmark-checklist tripwire and registers skill."""
    agents = _read("AGENTS.md")
    behaviors = _section_between(agents, "### Core Operating Behaviors", "## 4. Discoverable Global Skills")
    assert "benchmark-checklist" in behaviors, (
        "Empirical Grounding tripwire must reference benchmark-checklist"
    )
    assert "changeset" in behaviors.lower(), (
        "AGENTS.md tripwire must scope benchmark-checklist to changeset claims"
    )

    skills_section = _section_between(agents, "## 4. Discoverable Global Skills", "## 5.")
    assert "[benchmark-checklist/SKILL.md](skills/benchmark-checklist/SKILL.md)" in skills_section


def test_benchmark_review_gates():
    """Slice 1: review skills cross-reference @skill:benchmark-checklist."""
    adv = _read("skills/adversarial-review/SKILL.md")
    adv_perf = _section_between(adv, "5. **Perform Adversarial Review**", "6. **Output Report")
    assert "@skill:benchmark-checklist" in adv_perf
    adv_lower = adv_perf.lower()
    assert "limiter" in adv_lower and "tuned" in adv_lower and "ballpark" in adv_lower

    crq = _read("skills/code-review-and-quality/SKILL.md")
    crq_perf = _section_between(crq, "### 5. Performance", "### Domain Checklist:")
    assert "@skill:benchmark-checklist" in crq_perf


def test_statechart_gate_is_auditable():
    """Slice 2: spec-driven-development and adversarial-review enforce State transitions: gate."""
    sdd = _read("skills/spec-driven-development/SKILL.md")
    draft_section = _section_between(sdd, "### 2. Draft the Spec", "### 2b.")
    draft_lower = draft_section.lower()

    assert "State transitions:" in draft_section
    for trigger_term in ("background", "retry", "cancellation", "teardown"):
        assert trigger_term in draft_lower, f"Missing statechart trigger term: {trigger_term}"
    assert "ambiguity" in draft_lower and "inclusion" in draft_lower, (
        "Must state ambiguity-resolves-to-inclusion tie-break"
    )
    assert "n/a" in draft_lower and "reason" in draft_lower, (
        "Must require non-empty reason when declaring N/A"
    )

    adv = _read("skills/adversarial-review/SKILL.md")
    spec_checklist = _section_between(adv, "2. Apply mode-specific checklist:", "3. Output verdict")
    spec_lower = spec_checklist.lower()
    assert "State transitions:" in spec_checklist
    assert "n/a" in spec_lower
    for edge in ("illegal", "timeout", "error"):
        assert edge in spec_lower, f"spec-review checklist missing {edge} transition audit"


def test_downstream_consumer_trace_gates():
    """Slice 2: adversarial-review and ponytail require Downstream Consumer Trace beyond grep."""
    adv = _read("skills/adversarial-review/SKILL.md")
    adv_section = _section_between(adv, "5. **Perform Adversarial Review**", "6. **Output Report")
    adv_lower = adv_section.lower()
    assert "Downstream Consumer Trace" in adv_section
    assert "beyond" in adv_lower and "grep" in adv_lower
    assert "unproven" in adv_lower and "execution" in adv_lower

    ponytail = _read("skills/ponytail/SKILL.md")
    ponytail_lower = ponytail.lower()
    assert "Downstream Consumer Trace" in ponytail
    assert "indirect" in ponytail_lower and "grep" in ponytail_lower
    assert "execution" in ponytail_lower or "running code" in ponytail_lower


def test_unslop_tier_precedence_and_wiring():
    """Slice 3: prose-editor has --unslop tier + caveman precedence; external prose gates wire it inline."""
    pe = _read("skills/prose-editor/SKILL.md")
    triggers = _section_between(pe, "## Command Triggers", "## Core Principles")
    principles = _section_between(pe, "## Core Principles", "## Editing Tiers")
    tiers = _section_between(pe, "## Editing Tiers", "## Suggestion Card Schema")

    assert "--unslop" in triggers
    assert "--unslop" in tiers

    principles_lower = principles.lower()
    assert "unslop" in principles_lower and "caveman" in principles_lower, (
        "Core Principles must state precedence between --unslop and caveman"
    )
    assert "chat" in principles_lower and ("external" in principles_lower or "document" in principles_lower)

    tiers_lower = tiers.lower()
    for canonical_token in (
        "ai vocabulary",
        "em dash",
        "abstract metaphor nouns",
        "over-compression",
    ):
        assert canonical_token in tiers_lower, f"Missing canonical unslop token: {canonical_token}"

    mf = _read("skills/make-feature/SKILL.md")
    step_7c = _section_between(mf, "Step 7c", "5. **Phase 4")
    assert "[prose-editor](../prose-editor/SKILL.md)" in step_7c
    assert "--unslop" in step_7c and "inline" in step_7c.lower()
    assert "@skill:prose-editor" not in step_7c

    adv = _read("skills/adversarial-review/SKILL.md")
    adv_section = _section_between(adv, "5. **Perform Adversarial Review**", "6. **Output Report")
    assert "[prose-editor](../prose-editor/SKILL.md)" in adv_section
    assert "--unslop" in adv_section and "inline" in adv_section.lower()
    assert "@skill:prose-editor" not in adv_section


def test_agents_md_encode_lessons_rule():
    """Slice 3: AGENTS.md Key Rules under Ponytail includes Encode lessons in structure."""
    agents = _read("AGENTS.md")
    ponytail_rules = _section_between(agents, "### Key Rules", "## 2. Caveman")
    rules_lower = ponytail_rules.lower()
    assert "Encode lessons in structure" in ponytail_rules
    assert "linter" in rules_lower and "test" in rules_lower
