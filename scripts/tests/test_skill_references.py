import glob
import os
import re
import subprocess

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SKILLS_DIR = os.path.join(ROOT_DIR, "skills")


def _tracked_skill_markdown_files():
    """Return tracked markdown files under skills/ so gitignored auto-bundles do not pollute tests."""
    res = subprocess.run(
        ["git", "ls-files", "skills/"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode == 0 and res.stdout.strip():
        return [
            os.path.join(ROOT_DIR, line.strip())
            for line in res.stdout.splitlines()
            if line.strip().endswith(".md") and os.path.exists(os.path.join(ROOT_DIR, line.strip()))
        ]
    return glob.glob(os.path.join(SKILLS_DIR, "**/*.md"), recursive=True)


def _tracked_skill_names():
    """Return top-level tracked skill directory names under skills/."""
    res = subprocess.run(
        ["git", "ls-files", "skills/"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode == 0 and res.stdout.strip():
        names = set()
        for line in res.stdout.splitlines():
            parts = line.strip().split("/")
            if len(parts) >= 3 and parts[0] == "skills" and not parts[1].startswith("."):
                skill_dir = os.path.join(SKILLS_DIR, parts[1])
                if os.path.isdir(skill_dir):
                    names.add(parts[1])
        return sorted(names)
    return sorted(
        name
        for name in os.listdir(SKILLS_DIR)
        if os.path.isdir(os.path.join(SKILLS_DIR, name)) and not name.startswith(".")
    )


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

    if (name_value.startswith('"') and name_value.endswith('"')) or (
        name_value.startswith("'") and name_value.endswith("'")
    ):
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


def test_all_skill_references_resolve():
    """Verify that every @skill:<name> reference in tracked skills resolves to a valid skill."""
    skill_ref_pattern = re.compile(r"@skill:([a-zA-Z0-9_-]+)")

    errors = []
    for filepath in _tracked_skill_markdown_files():
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        for ref in skill_ref_pattern.findall(content):
            err = validate_skill_resolution(SKILLS_DIR, ref)
            if err:
                rel_path = os.path.relpath(filepath, SKILLS_DIR)
                errors.append(f"In {rel_path}: reference '@skill:{ref}' failed validation: {err}")

    assert not errors, "\n".join(errors)


def test_all_skills_have_correct_frontmatter_name():
    """Verify all tracked skill directories match their frontmatter names."""
    for skill_name in _tracked_skill_names():
        err = validate_skill_resolution(SKILLS_DIR, skill_name)
        assert err is None, f"Skill '{skill_name}' failed validation: {err}"


def test_no_skill_disables_model_invocation():
    """Permanent structural guard: no tracked skill may set disable-model-invocation: true."""
    violations = []
    for skill_name in _tracked_skill_names():
        skill_md = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        with open(skill_md, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        if not lines or lines[0] != "---":
            continue
        for line in lines[1:]:
            if line == "---":
                break
            if re.match(r"^disable-model-invocation:\s*true\s*(#.*)?$", line.strip(), re.IGNORECASE):
                violations.append(f"skills/{skill_name}/SKILL.md")
                break
    assert not violations, f"Skills disabling model invocation: {violations}"


def test_no_non_portable_file_links():
    """Verify that no tracked markdown file contains non-portable file:// URLs."""
    file_link_pattern = re.compile(r"\]\((file://[^\)]+)\)")

    errors = []
    for filepath in _tracked_skill_markdown_files():
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        for link in file_link_pattern.findall(content):
            rel_path = os.path.relpath(filepath, SKILLS_DIR)
            errors.append(f"In {rel_path}: file:// link found: '{link}'")

    assert not errors, "\n".join(errors)


def test_all_skill_relative_markdown_links_resolve():
    """Verify relative links outside code blocks/inline examples in tracked SKILL.md files resolve."""
    fence_re = re.compile(r"^\s*(`{3,}|~{3,}).*?^\s*\1", re.MULTILINE | re.DOTALL)
    link_re = re.compile(r"\]\((?!https?://|#|mailto:)([^)#]+)(?:#[^)]*)?\)")
    errors = []
    for skill_name in _tracked_skill_names():
        skill_md = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
        with open(skill_md, "r", encoding="utf-8") as f:
            content = fence_re.sub("", f.read())
        for rel_target in link_re.findall(content):
            if "<" in rel_target or ">" in rel_target or rel_target == "path/to/file":
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(skill_md), rel_target))
            if not os.path.exists(resolved):
                errors.append(f"In skills/{skill_name}/SKILL.md: broken link '{rel_target}' -> '{resolved}'")
    assert not errors, "\n".join(errors)


# Focused unit test cases for validate_skill_resolution
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
    (skill_dir / "SKILL.md").write_text("---\nname: different-name\n---\nbody")
    err = validate_skill_resolution(str(tmp_path), "mismatch-name")
    assert "mismatched frontmatter name" in err


def test_validation_leading_non_frontmatter(tmp_path):
    skill_dir = tmp_path / "leading-content"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("invalid leading content\n---\nname: leading-content\n---\nbody")
    err = validate_skill_resolution(str(tmp_path), "leading-content")
    assert "missing name in frontmatter" in err


def test_validation_missing_closing_delimiter(tmp_path):
    skill_dir = tmp_path / "no-closing"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: no-closing\nbody")
    err = validate_skill_resolution(str(tmp_path), "no-closing")
    assert "missing name in frontmatter" in err


def test_validation_name_extra_text(tmp_path):
    skill_dir = tmp_path / "extra-text"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: extra-text extra\n---\nbody")
    err = validate_skill_resolution(str(tmp_path), "extra-text")
    assert "missing name in frontmatter" in err


def test_validation_quoted_valid_name(tmp_path):
    skill_dir = tmp_path / "quoted-name"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text('---\nname: "quoted-name"\n---\nbody')
    err = validate_skill_resolution(str(tmp_path), "quoted-name")
    assert err is None


def test_streamlined_agents_and_adversarial_review_contract():
    """Verify streamlined AGENTS.md workflow rules and single-purpose adversarial-review contract."""
    agents_md = os.path.join(ROOT_DIR, "AGENTS.md")
    adv_md = os.path.join(SKILLS_DIR, "adversarial-review", "SKILL.md")
    gitignore_path = os.path.join(ROOT_DIR, ".gitignore")

    with open(agents_md, "r", encoding="utf-8") as f:
        agents_c = f.read()
    with open(adv_md, "r", encoding="utf-8") as f:
        adv_c = f.read()
    with open(gitignore_path, "r", encoding="utf-8") as f:
        gi_c = f.read()

    # Protected branch safety + in-place manual worktree support
    assert "edit in place" in agents_c.lower()
    assert "nested worktrees" in agents_c.lower()
    assert "/grill-me" in agents_c
    assert "/grillme" not in agents_c

    # Proportional tiers
    for tier in ["Trivial", "Standard", "Heavy"]:
        assert tier in agents_c

    # Adversarial review streamlined flags & sections
    for flag in ["--mode=external|pipeline", "--last-sha", "--force", "--pr", "--prune"]:
        assert flag in adv_c
    assert "Adversarial Audit Summary" in adv_c
    assert "External PR Action Plan" in adv_c
    assert "run_in_env.py" in adv_c

    # Legacy Arena / ephemeral review branch bloat removed
    for legacy_term in ["Reviewer Identification Proof", "TAMPERED/CLOBBERED", "review_prompt.md", "reviewer_scorecard.md"]:
        assert legacy_term not in agents_c
        assert legacy_term not in adv_c

    # Scratch and auto-bundled Data Cloud skills gitignored
    assert "scratch/" in gi_c
    assert "skills/.datacloud_skills_manifest" in gi_c


def test_catchmeup_skill_contract():
    """Verify catchmeup SKILL.md presets, read-only scratch safety, trailer parsing, and @skill references."""
    catchmeup_md = os.path.join(SKILLS_DIR, "catchmeup", "SKILL.md")
    readme_md = os.path.join(ROOT_DIR, "README.md")
    agents_md = os.path.join(ROOT_DIR, "AGENTS.md")

    with open(catchmeup_md, "r", encoding="utf-8") as f:
        catchmeup_content = f.read()
    with open(readme_md, "r", encoding="utf-8") as f:
        readme_content = f.read()
    with open(agents_md, "r", encoding="utf-8") as f:
        agents_content = f.read()

    for preset in ["1d", "1w", "2w", "1mo"]:
        assert preset in catchmeup_content

    assert "Creating temporary, ephemeral scratch files under the conversation's scratch directory" in catchmeup_content
    assert 'rm -- "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_' in catchmeup_content
    assert "view_file" in catchmeup_content and "<=800-line" in catchmeup_content
    assert "%(trailers:key=Signoff-*" not in catchmeup_content
    assert "%(trailers:key=Signoff-Reviewed-Commit-SHA" in catchmeup_content
    assert "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST" in catchmeup_content
    assert "--invert-grep" in catchmeup_content

    grammar_match = re.search(r"- \*\*Accepted Grammar\*\*: `(.*?)`", catchmeup_content)
    assert grammar_match
    grammar_pattern = re.compile(grammar_match.group(1))
    for table_arg in ["1d", "1 day", "1w", "1 week", "2w", "2 weeks", "1mo", "1 month"]:
        assert grammar_pattern.match(table_arg)

    assert "@skill:explain-diff" in catchmeup_content
    assert "../git-signoff/SKILL.md" in catchmeup_content
    assert "`catchmeup`" in readme_content
    assert "catchmeup/SKILL.md" in agents_content


def test_signoff_socratic_remediation_rule():
    """Verify vendored skills/git-signoff/SKILL.md defines Socratic remediation rules."""
    signoff_md = os.path.join(SKILLS_DIR, "git-signoff", "SKILL.md")
    assert os.path.exists(signoff_md)

    with open(signoff_md, "r", encoding="utf-8") as f:
        signoff_content = f.read()

    section_match = re.search(r"Evaluation & Remediation:\s*(.*?)(?=\n### |\n## |\Z)", signoff_content, re.DOTALL)
    assert section_match
    remediation_text = section_match.group(1)

    assert any(term in remediation_text for term in ["not sure", "uncertainty"])
    assert "vague" in remediation_text or "hand-waving" in remediation_text
    assert "pause signoff" in remediation_text
    assert "@skill:explain-diff" in remediation_text
    assert "re-probe" in remediation_text
    assert "Worktree Target Mandate" in signoff_content
    assert "worktree_path" in signoff_content


def test_signoff_gsa_protocol_spec_and_trailers():
    """Verify GSA Protocol spec and skills/git-signoff/SKILL.md trailer/adapter contracts."""
    spec_md = os.path.join(SKILLS_DIR, "git-signoff", "specs", "gsa-core.md")
    signoff_md = os.path.join(SKILLS_DIR, "git-signoff", "SKILL.md")

    with open(spec_md, "r", encoding="utf-8") as f:
        spec_content = f.read()
    with open(signoff_md, "r", encoding="utf-8") as f:
        signoff_content = f.read()

    for anchor in ["Protocol Specification", "Cryptographic Developer Identity Binding", "cat_sort_uniq", "ack_no_transcript"]:
        assert anchor in spec_content

    for trailer in ["Signoff-Spec-Version: 1.0", "Signoff-Harness-ID", "Signoff-Transcript-Bytes"]:
        assert trailer in signoff_content

    for adapter_env in ["GIT_SIGNOFF_TRANSCRIPT_FILE", "ANTIGRAVITY_CONVERSATION_ID", "CLAUDE_CODE_SESSION_ID"]:
        assert adapter_env in signoff_content

    assert "git-common-dir" in signoff_content
    assert "refs/notes/signoff" in signoff_content
    assert "cat_sort_uniq" in signoff_content
    assert "refs/notes/signoff-remote" in spec_content
    assert "user.signingkey" in signoff_content
    assert "specs/gsa-core.md" in signoff_content


PROFILE_BLOCK_RE = re.compile(
    r"<!-- INTERVIEW-PROFILE:BEGIN[^>]*-->\n(.*?)<!-- INTERVIEW-PROFILE:END -->",
    re.DOTALL,
)


def _extract_profile_block(content, source):
    blocks = PROFILE_BLOCK_RE.findall(content)
    assert len(blocks) == 1, f"Expected exactly one INTERVIEW PROFILE block in {source}, found {len(blocks)}"
    return blocks[0]


def test_signoff_phase3c_interview_contract():
    """Verify Signoff-Agent provenance grammar, named intensity levels, and swappable INTERVIEW PROFILE block."""
    signoff_md = os.path.join(SKILLS_DIR, "git-signoff", "SKILL.md")
    spec_md = os.path.join(SKILLS_DIR, "git-signoff", "specs", "gsa-core.md")
    harnesses_md = os.path.join(SKILLS_DIR, "git-signoff", "HARNESSES.md")
    default_profile_md = os.path.join(SKILLS_DIR, "git-signoff", "profiles", "software-general.md")
    science_profile_md = os.path.join(SKILLS_DIR, "git-signoff", "profiles", "domain-science.md")

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

    for token in ["harness=", "model=", "reasoning=", "interview="]:
        assert token in signoff_content
        assert token in spec_content
    assert "N/A" in spec_content
    for env_var in ["CLAUDE_CODE_VERSION", "CLAUDE_EFFORT", "ANTHROPIC_MODEL"]:
        assert env_var in signoff_content

    for level in ["cursory", "standard", "skeptical"]:
        assert level in signoff_content
    assert "--quick" in signoff_content and "--deep" in signoff_content
    assert "Interview Intensity Levels" in signoff_content
    assert "prediction challenge" in signoff_content

    embedded_block = _extract_profile_block(signoff_content, "skills/git-signoff/SKILL.md")
    default_block = _extract_profile_block(default_profile_content, "skills/git-signoff/profiles/software-general.md")
    assert embedded_block == default_block

    for block, source in [
        (embedded_block, "skills/git-signoff/SKILL.md"),
        (science_profile_content, "skills/git-signoff/profiles/domain-science.md"),
    ]:
        assert re.search(r"^Profile-ID:\s*([a-z0-9-]+)\s*$", block, re.MULTILINE), f"Missing Profile-ID in {source}"
    assert "Profile-ID: software-general" in embedded_block
    assert "Profile-ID: domain-science" in science_profile_content
    assert "sole customization point" in signoff_content
    assert "sole customization point" in harnesses_content
    assert "profiles/software-general.md" in harnesses_content
    assert "profiles/domain-science.md" in harnesses_content


def test_no_deprecated_signoff_references():
    """Verify no tracked skill markdown file uses deprecated @skill:signoff or skills/signoff/."""
    skill_ref_pattern = re.compile(r"@skill:signoff\b")
    link_ref_pattern = re.compile(r"skills/signoff/")

    errors = []
    for filepath in _tracked_skill_markdown_files():
        rel_path = os.path.relpath(filepath, ROOT_DIR)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if skill_ref_pattern.search(content):
            errors.append(f"In {rel_path}: deprecated '@skill:signoff' found")
        if link_ref_pattern.search(content):
            errors.append(f"In {rel_path}: deprecated 'skills/signoff/' link found")

    assert not errors, "\n".join(errors)
