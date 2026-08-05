"""Skill contract tests for the standalone signoff repo.

Trimmed from dotgemini's scripts/tests/test_skill_references.py (whose history
this file carries): only the signoff-relevant contracts remain. Cross-skill
references to skills not shipped in this repo (e.g. @skill:explain-diff) are
allowed when documented as degrading gracefully in HARNESSES.md portability
rules; everything else must resolve to a valid in-repo skill.
"""

import glob
import os
import re

# External skills referenced by signoff that degrade gracefully when absent
# (HARNESSES.md, Portability Rules #3).
GRACEFUL_EXTERNAL_SKILLS = {"explain-diff", "make-feature"}


def parse_frontmatter_name(skill_md_path):
    """Parse name from YAML frontmatter without external YAML parser dependency."""
    if not os.path.exists(skill_md_path):
        return None
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        return None

    lines = content.splitlines()
    if not lines or lines[0] != "---":
        return None

    closing_idx = -1
    for i in range(1, len(lines)):
        if lines[i] == "---":
            closing_idx = i
            break

    if closing_idx == -1:
        return None

    frontmatter_lines = lines[1:closing_idx]

    name_value = None
    for line in frontmatter_lines:
        match = re.match(r"^name:\s*(.+)$", line)
        if match:
            name_value = match.group(1).strip()
            break

    if not name_value:
        return None

    if (name_value.startswith('"') and name_value.endswith('"')) or (name_value.startswith("'") and name_value.endswith("'")):
        name_value = name_value[1:-1].strip()

    if not re.match(r"^[a-zA-Z0-9_-]+$", name_value):
        return None

    return name_value


def validate_skill_resolution(skills_dir, skill_name):
    """Validate skill folder structure and frontmatter name."""
    skill_path = os.path.join(skills_dir, skill_name)
    if not os.path.exists(skill_path) or not os.path.isdir(skill_path):
        return f"Directory skills/{skill_name} does not exist."

    skill_md_path = os.path.join(skill_path, "SKILL.md")
    if not os.path.exists(skill_md_path):
        return f"File skills/{skill_name}/SKILL.md does not exist."

    fm_name = parse_frontmatter_name(skill_md_path)
    if not fm_name:
        return f"skills/{skill_name}/SKILL.md is missing name in frontmatter."

    if fm_name != skill_name:
        return f"skills/{skill_name}/SKILL.md has mismatched frontmatter name '{fm_name}' (expected '{skill_name}')."

    return None


def _skills_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../skills"))


def test_all_skill_references_resolve_or_degrade_gracefully():
    """Every @skill:<name> reference resolves in-repo or is a documented graceful-degradation external."""
    skills_dir = _skills_dir()
    skill_ref_pattern = re.compile(r"@skill:([a-zA-Z0-9_-]+)")

    errors = []
    markdown_files = glob.glob(os.path.join(skills_dir, "**/*.md"), recursive=True)
    assert markdown_files, "no markdown files found under skills/"
    for filepath in markdown_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        for ref in skill_ref_pattern.findall(content):
            if ref in GRACEFUL_EXTERNAL_SKILLS:
                continue
            err = validate_skill_resolution(skills_dir, ref)
            if err:
                rel_path = os.path.relpath(filepath, skills_dir)
                errors.append(f"In {rel_path}: reference '@skill:{ref}' failed validation: {err}")

    assert not errors, "\n".join(errors)


def test_all_skills_have_correct_frontmatter_name():
    """Verify all existing skill directories match their frontmatter names."""
    skills_dir = _skills_dir()
    for skill_name in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, skill_name)
        if os.path.isdir(skill_path) and not skill_name.startswith("."):
            err = validate_skill_resolution(skills_dir, skill_name)
            assert err is None, f"Skill '{skill_name}' failed validation: {err}"


def test_no_non_portable_file_links():
    """Verify that no markdown file contains file:// URLs (prohibited for portability)."""
    skills_dir = _skills_dir()
    file_link_pattern = re.compile(r"\]\((file://[^\)]+)\)")

    errors = []
    markdown_files = glob.glob(os.path.join(skills_dir, "**/*.md"), recursive=True)
    for filepath in markdown_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        for link in file_link_pattern.findall(content):
            rel_path = os.path.relpath(filepath, skills_dir)
            errors.append(f"In {rel_path}: file:// link found: '{link}' (file:// links are prohibited)")

    assert not errors, "\n".join(errors)


def test_skill_folder_is_self_contained():
    """No relative markdown link inside skills/signoff may escape the folder (Phase 3a)."""
    skills_dir = _skills_dir()
    signoff_dir = os.path.join(skills_dir, "signoff")
    link_pattern = re.compile(r"\]\(([^)#\s]+)")

    errors = []
    for filepath in glob.glob(os.path.join(signoff_dir, "**/*.md"), recursive=True):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        for target in link_pattern.findall(content):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target):  # URLs (https:, mailto:, ...)
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(filepath), target))
            if not resolved.startswith(signoff_dir + os.sep):
                rel = os.path.relpath(filepath, skills_dir)
                errors.append(f"In {rel}: link '{target}' escapes skills/signoff")

    assert not errors, "\n".join(errors)


# Focused test cases using pytest tmp_path
def test_validation_missing_directory(tmp_path):
    err = validate_skill_resolution(str(tmp_path), "missing-skill")
    assert "does not exist" in err


def test_validation_missing_skill_md(tmp_path):
    skill_dir = tmp_path / "no-skill-md"
    skill_dir.mkdir()
    err = validate_skill_resolution(str(tmp_path), "no-skill-md")
    assert "SKILL.md does not exist" in err


def test_validation_mismatched_frontmatter_name(tmp_path):
    skill_dir = tmp_path / "mismatch-name"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: different-name\n---\nbody")
    err = validate_skill_resolution(str(tmp_path), "mismatch-name")
    assert "mismatched frontmatter name" in err


def test_validation_quoted_valid_name(tmp_path):
    skill_dir = tmp_path / "quoted-name"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: \"quoted-name\"\n---\nbody")
    err = validate_skill_resolution(str(tmp_path), "quoted-name")
    assert err is None


def test_signoff_socratic_remediation_rule():
    """Verify skills/signoff/SKILL.md defines hardened Socratic remediation rules."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    signoff_md = os.path.join(root_dir, "skills/signoff/SKILL.md")

    assert os.path.exists(signoff_md), "skills/signoff/SKILL.md does not exist"

    with open(signoff_md, "r", encoding="utf-8") as f:
        signoff_content = f.read()

    assert "Evaluation & Remediation" in signoff_content, "Missing Evaluation & Remediation in skills/signoff/SKILL.md"

    section_match = re.search(r"Evaluation & Remediation:\s*(.*?)(?=\n### |\n## |\Z)", signoff_content, re.DOTALL)
    assert section_match, "Could not extract Evaluation & Remediation section from skills/signoff/SKILL.md"
    remediation_text = section_match.group(1)

    assert any(term in remediation_text for term in ["not sure", "uncertainty"]), "Missing uncertainty trigger in remediation rule"
    assert "vague" in remediation_text or "hand-waving" in remediation_text, "Missing vague/hand-waving trigger in remediation rule"
    assert "pause signoff" in remediation_text, "Missing 'pause signoff' in remediation rule"
    assert "@skill:explain-diff" in remediation_text, "Missing '@skill:explain-diff' reference in remediation rule"
    assert "re-probe" in remediation_text, "Missing re-probing requirement in remediation rule"

    assert "Worktree Target Mandate" in signoff_content, "Missing Worktree Target Mandate in skills/signoff/SKILL.md"
    assert "worktree_path" in signoff_content, "Missing 'worktree_path' in skills/signoff/SKILL.md Section 4"


def test_signoff_gsa_protocol_spec_and_trailers():
    """Verify the GSA Protocol core spec exists and skills/signoff/SKILL.md implements its portable trailer schema, harness adapters, and Git Notes persistence."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    spec_md = os.path.join(root_dir, "skills/signoff/specs/gsa-core.md")
    signoff_md = os.path.join(root_dir, "skills/signoff/SKILL.md")

    assert os.path.exists(spec_md), "skills/signoff/specs/gsa-core.md does not exist"

    with open(spec_md, "r", encoding="utf-8") as f:
        spec_content = f.read()

    for anchor in [
        "Protocol Specification",
        "Cryptographic Developer Identity Binding",
        "cat_sort_uniq",
        "ack_no_transcript",
    ]:
        assert anchor in spec_content, f"Missing '{anchor}' in skills/signoff/specs/gsa-core.md"

    with open(signoff_md, "r", encoding="utf-8") as f:
        signoff_content = f.read()

    for trailer in [
        "Signoff-Spec-Version: 1.0",
        "Signoff-Harness-ID",
        "Signoff-Transcript-Bytes",
    ]:
        assert trailer in signoff_content, f"Missing '{trailer}' trailer in skills/signoff/SKILL.md"

    for adapter_env in [
        "SIGNOFF_TRANSCRIPT_FILE",
        "ANTIGRAVITY_CONVERSATION_ID",
        "CLAUDE_CODE_SESSION_ID",
    ]:
        assert adapter_env in signoff_content, f"Missing '{adapter_env}' adapter resolution in skills/signoff/SKILL.md"

    assert "--git-common-dir" in signoff_content, "Missing worktree git-common-dir fallback in skills/signoff/SKILL.md"

    assert "refs/notes/signoff" in signoff_content, "Missing 'refs/notes/signoff' persistence in skills/signoff/SKILL.md"
    assert "cat_sort_uniq" in signoff_content, "Missing 'cat_sort_uniq' notes merge strategy in skills/signoff/SKILL.md"
    assert "refs/notes/signoff-remote" in signoff_content, "Missing tracking-ref fetch for notes merge in skills/signoff/SKILL.md"

    assert "user.signingkey" in signoff_content, "Missing signed-commit support (user.signingkey) in skills/signoff/SKILL.md"

    assert "specs/gsa-core.md" in signoff_content, "Missing specs/gsa-core.md reference in skills/signoff/SKILL.md"


PROFILE_BLOCK_RE = re.compile(
    r"<!-- INTERVIEW-PROFILE:BEGIN[^>]*-->\n(.*?)<!-- INTERVIEW-PROFILE:END -->",
    re.DOTALL,
)


def _extract_profile_block(content, source):
    blocks = PROFILE_BLOCK_RE.findall(content)
    assert len(blocks) == 1, f"Expected exactly one INTERVIEW PROFILE block in {source}, found {len(blocks)}"
    return blocks[0]


def test_signoff_phase3c_interview_contract():
    """Verify Phase 3c: Signoff-Agent provenance grammar, named intensity levels, and the single swappable INTERVIEW PROFILE block."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    signoff_md = os.path.join(root_dir, "skills/signoff/SKILL.md")
    spec_md = os.path.join(root_dir, "skills/signoff/specs/gsa-core.md")
    harnesses_md = os.path.join(root_dir, "skills/signoff/HARNESSES.md")
    default_profile_md = os.path.join(root_dir, "skills/signoff/profiles/software-general.md")
    science_profile_md = os.path.join(root_dir, "skills/signoff/profiles/domain-science.md")

    for path in [signoff_md, spec_md, harnesses_md, default_profile_md, science_profile_md]:
        assert os.path.exists(path), f"{os.path.relpath(path, root_dir)} does not exist"

    with open(signoff_md, "r", encoding="utf-8") as f:
        signoff_content = f.read()
    with open(spec_md, "r", encoding="utf-8") as f:
        spec_content = f.read()
    with open(harnesses_md, "r", encoding="utf-8") as f:
        harnesses_content = f.read()
    with open(default_profile_md, "r", encoding="utf-8") as f:
        default_profile_content = f.read()
    with open(science_profile_md, "r", encoding="utf-8") as f:
        science_profile_content = f.read()

    # (1) Signoff-Agent provenance grammar defined in the spec and used by the skill
    for token in ["harness=", "model=", "reasoning=", "interview="]:
        assert token in signoff_content, f"Signoff-Agent grammar token '{token}' missing from skills/signoff/SKILL.md"
        assert token in spec_content, f"Signoff-Agent grammar token '{token}' missing from skills/signoff/specs/gsa-core.md"
    assert "N/A" in spec_content, "Missing N/A convention for unexposed provenance fields in gsa-core.md"
    for env_var in ["CLAUDE_CODE_VERSION", "CLAUDE_EFFORT", "ANTHROPIC_MODEL"]:
        assert env_var in signoff_content, f"Deterministic provenance source '{env_var}' missing from skills/signoff/SKILL.md"

    # (2) Named intensity levels formalizing --quick/--deep
    for level in ["cursory", "standard", "skeptical"]:
        assert level in signoff_content, f"Intensity level '{level}' missing from skills/signoff/SKILL.md"
    assert "--quick" in signoff_content and "--deep" in signoff_content, "Missing --quick/--deep modifier mapping in skills/signoff/SKILL.md"
    assert "Interview Intensity Levels" in signoff_content, "Missing Interview Intensity Levels section in skills/signoff/SKILL.md"
    assert "prediction challenge" in signoff_content, "Missing skeptical-level prediction challenges in skills/signoff/SKILL.md"

    # (3) Exactly one delimited INTERVIEW PROFILE block, byte-identical to the shipped default
    embedded_block = _extract_profile_block(signoff_content, "skills/signoff/SKILL.md")
    default_block = _extract_profile_block(default_profile_content, "skills/signoff/profiles/software-general.md")
    assert embedded_block == default_block, (
        "Embedded INTERVIEW PROFILE block in SKILL.md diverged from profiles/software-general.md"
    )

    for block, source in [
        (embedded_block, "skills/signoff/SKILL.md"),
        (science_profile_content, "skills/signoff/profiles/domain-science.md"),
    ]:
        pid = re.search(r"^Profile-ID:\s*([a-z0-9-]+)\s*$", block, re.MULTILINE)
        assert pid, f"Missing or malformed Profile-ID in {source}"
    assert "Profile-ID: software-general" in embedded_block, "Default embedded profile must be software-general"
    assert "Profile-ID: domain-science" in science_profile_content, "domain-science profile must declare its Profile-ID"

    assert "sole customization point" in signoff_content, "Missing 'sole customization point' marker in skills/signoff/SKILL.md"
    assert "sole customization point" in harnesses_content, "Missing 'sole customization point' documentation in skills/signoff/HARNESSES.md"
    assert "profiles/software-general.md" in harnesses_content, "Missing software-general profile reference in HARNESSES.md"
    assert "profiles/domain-science.md" in harnesses_content, "Missing domain-science profile reference in HARNESSES.md"
