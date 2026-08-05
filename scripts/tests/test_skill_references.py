import glob
import os
import re
import subprocess

def parse_frontmatter_name(skill_md_path):
    """Parse name from YAML frontmatter without external YAML parser dependency."""
    if not os.path.exists(skill_md_path):
        return None
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Requirement 1: must start with --- at byte zero
    if not content.startswith("---"):
        return None
        
    # Requirement 2: locate closing delimiter on its own line
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
        
    # Requirement 3: parse only the frontmatter block
    frontmatter_lines = lines[1:closing_idx]
    
    # Locate name line
    name_value = None
    for line in frontmatter_lines:
        match = re.match(r"^name:\s*(.+)$", line)
        if match:
            name_value = match.group(1).strip()
            break
            
    if not name_value:
        return None
        
    # Requirement 5: handle surrounding single or double quotes
    if (name_value.startswith('"') and name_value.endswith('"')) or (name_value.startswith("'") and name_value.endswith("'")):
        name_value = name_value[1:-1].strip()
        
    # Requirement 4: require the entire name to match the expected skill-name grammar
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
    """Verify that every @skill:<name> reference in skills/ resolves to a valid, loadable skill."""
    skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../skills"))
    
    # Regex to find @skill:<name> (handling markdown bold formatting around it if any)
    skill_ref_pattern = re.compile(r"@skill:([a-zA-Z0-9_-]+)")
    
    errors = []
    # Scan all markdown files in skills/ recursively
    markdown_files = glob.glob(os.path.join(skills_dir, "**/*.md"), recursive=True)
    for filepath in markdown_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        matches = skill_ref_pattern.findall(content)
        for ref in matches:
            err = validate_skill_resolution(skills_dir, ref)
            if err:
                rel_path = os.path.relpath(filepath, skills_dir)
                errors.append(f"In {rel_path}: reference '@skill:{ref}' failed validation: {err}")
                
    assert not errors, "\n".join(errors)

def test_all_skills_have_correct_frontmatter_name():
    """Verify all existing skill directories match their frontmatter names."""
    skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../skills"))
    for skill_name in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, skill_name)
        if os.path.isdir(skill_path) and not skill_name.startswith("."):
            err = validate_skill_resolution(skills_dir, skill_name)
            assert err is None, f"Skill '{skill_name}' failed validation: {err}"

def test_no_non_portable_file_links():
    """Verify that no markdown file contains file:// URLs (all file:// links are prohibited to ensure portability)."""
    skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../skills"))
    
    # Matches markdown link target starting with file://
    file_link_pattern = re.compile(r"\]\((file://[^\)]+)\)")
    
    errors = []
    markdown_files = glob.glob(os.path.join(skills_dir, "**/*.md"), recursive=True)
    for filepath in markdown_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        links = file_link_pattern.findall(content)
        for link in links:
            rel_path = os.path.relpath(filepath, skills_dir)
            errors.append(f"In {rel_path}: file:// link found: '{link}' (file:// links are prohibited)")
                    
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

def test_validation_leading_non_frontmatter(tmp_path):
    skill_dir = tmp_path / "leading-content"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("invalid leading content\n---\nname: leading-content\n---\nbody")
    err = validate_skill_resolution(str(tmp_path), "leading-content")
    assert "missing name in frontmatter" in err

def test_validation_missing_closing_delimiter(tmp_path):
    skill_dir = tmp_path / "no-closing"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: no-closing\nbody")
    err = validate_skill_resolution(str(tmp_path), "no-closing")
    assert "missing name in frontmatter" in err

def test_validation_name_extra_text(tmp_path):
    skill_dir = tmp_path / "extra-text"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: extra-text extra\n---\nbody")
    err = validate_skill_resolution(str(tmp_path), "extra-text")
    assert "missing name in frontmatter" in err

def test_validation_quoted_valid_name(tmp_path):
    skill_dir = tmp_path / "quoted-name"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: \"quoted-name\"\n---\nbody")
    err = validate_skill_resolution(str(tmp_path), "quoted-name")
    assert err is None


def test_retained_reasoning_and_compaction_rules_exist():
    """Verify that AGENTS.md and make-feature SKILL.md contain retained reasoning & compaction rules with strict path safety."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    agents_md = os.path.join(root_dir, "AGENTS.md")
    make_feature_md = os.path.join(root_dir, "skills/make-feature/SKILL.md")

    with open(agents_md, "r", encoding="utf-8") as f:
        agents_content = f.read()

    with open(make_feature_md, "r", encoding="utf-8") as f:
        make_feature_content = f.read()

    literal_scratchpad_path = "<appDataDir>/brain/<conversation-id>/scratch/scratchpad.md"
    assert literal_scratchpad_path in agents_content, f"Exact path '{literal_scratchpad_path}' missing from AGENTS.md"
    assert literal_scratchpad_path in make_feature_content, f"Exact path '{literal_scratchpad_path}' missing from make-feature SKILL.md"

    # Scan ONLY git-tracked markdown files to exclude untracked local noise or scratch directories
    res = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=root_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked_md_files = [
        os.path.join(root_dir, line.strip())
        for line in res.stdout.splitlines()
        if line.strip()
    ]

    # Only assert when scratchpad.md is preceded by a path segment or slash
    path_ref_pattern = re.compile(r"[\w~<>./-]+/scratchpad\.md")
    for md_path in tracked_md_files:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        matches = path_ref_pattern.findall(content)
        for match in matches:
            assert match == literal_scratchpad_path, (
                f"Non-canonical scratchpad path reference '{match}' found in {md_path}"
            )

    # Verify the 5 compaction fields are consistent across AGENTS.md and SKILL.md
    required_fields = [
        "Feature Rationale",
        "Key Architectural Decisions",
        "Active Constraints",
        "Prior Step Findings",
        "Target Artifact Paths",
    ]
    for field in required_fields:
        assert field in agents_content, f"Compaction field '{field}' missing from AGENTS.md"
        assert field in make_feature_content, f"Compaction field '{field}' missing from make-feature SKILL.md"


def test_sequential_subagent_slicing_consistency():
    """Verify that Sequential Subagent Slicing guidelines, canonical thresholds, and safety rules are consistent across skill files."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    inc_md = os.path.join(root_dir, "skills/incremental-implementation/SKILL.md")
    plan_md = os.path.join(root_dir, "skills/planning-and-task-breakdown/SKILL.md")
    make_feature_md = os.path.join(root_dir, "skills/make-feature/SKILL.md")

    with open(inc_md, "r", encoding="utf-8") as f:
        inc_content = f.read()
    with open(plan_md, "r", encoding="utf-8") as f:
        plan_content = f.read()
    with open(make_feature_md, "r", encoding="utf-8") as f:
        make_feature_content = f.read()

    assert "Sequential Subagent Slicing" in inc_content, "Missing Sequential Subagent Slicing in incremental-implementation"
    assert "Execution Strategy" in plan_content, "Missing Execution Strategy in planning-and-task-breakdown"
    assert "Sequential Subagent Delegation" in make_feature_content, "Missing Sequential Subagent Delegation in make-feature"

    # Precise threshold harmonization assertions
    canonical_threshold = "5 or more complex multi-file slices"
    assert canonical_threshold in inc_content, f"Canonical threshold '{canonical_threshold}' missing from incremental-implementation"
    assert canonical_threshold in plan_content, f"Canonical threshold '{canonical_threshold}' missing from planning-and-task-breakdown"
    assert ">5 heavy slices" not in inc_content, "Obsolete threshold '>5 heavy slices' found in incremental-implementation"
    assert ">5 heavy slices" not in plan_content, "Obsolete threshold '>5 heavy slices' found in planning-and-task-breakdown"

    # Execution safety, environment wrapper, and handoff rule assertions
    assert "Single Active Writer" in inc_content, "Missing Single Active Writer rule in incremental-implementation"
    assert "Pre-Dispatch Verification Gate" in inc_content, "Missing Pre-Dispatch Verification Gate in incremental-implementation"
    assert "Failure Circuit Breaker" in inc_content, "Missing Failure Circuit Breaker in incremental-implementation"
    assert "git add -- <intended-paths>" in inc_content, "Missing safe path-specific staging instruction in incremental-implementation"
    assert "parent conversation ID" in inc_content, "Missing explicit parent conversation ID scratchpad reference in incremental-implementation"
    assert "python3 ~/.gemini/scripts/run_in_env.py <worktree_path> pytest" in inc_content, "Missing environment wrapper pytest command in incremental-implementation"
    assert "python3 ~/.gemini/scripts/run_in_env.py <worktree_path> ruff check ." in inc_content, "Missing environment wrapper ruff command in incremental-implementation"

    # Strategy selection checkbox assertion
    assert "ensuring exactly one strategy checkbox is selected" in plan_content, "Missing single strategy checkbox assertion in planning-and-task-breakdown"


def test_catchmeup_skill_contract():
    """Verify that catchmeup SKILL.md contains required presets, read-only exception, cleanup instructions, trailer parsing, and @skill references."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    catchmeup_md = os.path.join(root_dir, "skills/catchmeup/SKILL.md")
    readme_md = os.path.join(root_dir, "README.md")
    agents_md = os.path.join(root_dir, "AGENTS.md")

    assert os.path.exists(catchmeup_md), "skills/catchmeup/SKILL.md does not exist"

    with open(catchmeup_md, "r", encoding="utf-8") as f:
        catchmeup_content = f.read()
    with open(readme_md, "r", encoding="utf-8") as f:
        readme_content = f.read()
    with open(agents_md, "r", encoding="utf-8") as f:
        agents_content = f.read()

    # Preset assertions
    for preset in ["1d", "1w", "2w", "1mo"]:
        assert preset in catchmeup_content, f"Preset '{preset}' missing from catchmeup SKILL.md"

    # Read-only contract & ephemeral scratch file exception assertion
    assert "Creating temporary, ephemeral scratch files under the conversation's scratch directory" in catchmeup_content, \
        "Missing ephemeral scratch file read-only exception in catchmeup SKILL.md"
    assert 'rm -- "<appDataDir>/brain/<conversation-id>/scratch/temp_catchmeup_' in catchmeup_content, \
        "Missing explicit rm -- cleanup instruction in catchmeup SKILL.md"
    assert "view_file" in catchmeup_content and "<=800-line" in catchmeup_content, \
        "Missing view_file <=800-line reading instruction in catchmeup SKILL.md"

    # Attestation parsing assertion (must use explicit keys, never broken glob %(trailers:key=Signoff-*)
    assert "%(trailers:key=Signoff-*" not in catchmeup_content, \
        "Broken trailer glob %(trailers:key=Signoff-*) found in catchmeup SKILL.md"
    assert "%(trailers:key=Signoff-Reviewed-Commit-SHA" in catchmeup_content, \
        "Missing explicit key %(trailers:key=Signoff-Reviewed-Commit-SHA... in catchmeup SKILL.md"
    assert "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST" in catchmeup_content, \
        "Missing VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST handling in catchmeup SKILL.md"
    assert "--invert-grep" in catchmeup_content, \
        "Missing --invert-grep attestation exclusion filter in catchmeup SKILL.md"

    # Dynamic duration grammar regex extraction test against advertised preset table values
    grammar_match = re.search(r"- \*\*Accepted Grammar\*\*: `(.*?)`", catchmeup_content)
    assert grammar_match, "Accepted Grammar pattern missing from catchmeup SKILL.md"
    grammar_pattern = re.compile(grammar_match.group(1))
    for table_arg in ["1d", "1 day", "1w", "1 week", "2w", "2 weeks", "1mo", "1 month"]:
        assert grammar_pattern.match(table_arg), f"Extracted grammar regex failed to match table argument '{table_arg}'"

    # Reference assertion
    assert "@skill:explain-diff" in catchmeup_content, \
        "Missing @skill:explain-diff reference in catchmeup SKILL.md"

    # Registration assertion
    assert "`catchmeup`" in readme_content, "Missing catchmeup registration in README.md"
    assert "catchmeup/SKILL.md" in agents_content, "Missing catchmeup indexing in AGENTS.md"


def test_heavy_mode_documented_consistently():
    """Verify that /make-feature heavy is documented consistently across README.md, make-feature, planning-and-task-breakdown, and incremental-implementation."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    readme_md = os.path.join(root_dir, "README.md")
    make_feature_md = os.path.join(root_dir, "skills/make-feature/SKILL.md")
    plan_md = os.path.join(root_dir, "skills/planning-and-task-breakdown/SKILL.md")
    inc_md = os.path.join(root_dir, "skills/incremental-implementation/SKILL.md")

    with open(readme_md, "r", encoding="utf-8") as f:
        readme_content = f.read()
    with open(make_feature_md, "r", encoding="utf-8") as f:
        make_feature_content = f.read()
    with open(plan_md, "r", encoding="utf-8") as f:
        plan_content = f.read()
    with open(inc_md, "r", encoding="utf-8") as f:
        inc_content = f.read()

    canonical_heavy_phrase = "proactively selects `Sequential Subagents` execution strategy"

    assert "/make-feature heavy" in readme_content, "Missing /make-feature heavy in README.md"
    assert "/make-feature heavy" in make_feature_content, "Missing /make-feature heavy in make-feature SKILL.md"
    assert "/make-feature heavy" in plan_content, "Missing /make-feature heavy in planning-and-task-breakdown SKILL.md"
    assert "/make-feature heavy" in inc_content, "Missing /make-feature heavy in incremental-implementation SKILL.md"

    assert canonical_heavy_phrase in readme_content, "Canonical heavy phrase missing from README.md"
    assert canonical_heavy_phrase in make_feature_content, "Canonical heavy phrase missing from make-feature SKILL.md"
    assert canonical_heavy_phrase in plan_content, "Canonical heavy phrase missing from planning-and-task-breakdown SKILL.md"
    assert canonical_heavy_phrase in inc_content, "Canonical heavy phrase missing from incremental-implementation SKILL.md"


def test_signoff_socratic_remediation_rule():
    """Verify that skills/signoff/SKILL.md and skills/math-proof-audit/SKILL.md define hardened Socratic remediation rules for uncertainty and vague answers."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    signoff_md = os.path.join(root_dir, "skills/signoff/SKILL.md")
    math_proof_md = os.path.join(root_dir, "skills/math-proof-audit/SKILL.md")

    assert os.path.exists(signoff_md), "skills/signoff/SKILL.md does not exist"
    assert os.path.exists(math_proof_md), "skills/math-proof-audit/SKILL.md does not exist"

    with open(signoff_md, "r", encoding="utf-8") as f:
        signoff_content = f.read()

    assert "Evaluation & Remediation" in signoff_content, "Missing Evaluation & Remediation in skills/signoff/SKILL.md"

    # Extract Evaluation & Remediation section from signoff SKILL.md
    section_match = re.search(r"Evaluation & Remediation:\s*(.*?)(?=\n### |\n## |\Z)", signoff_content, re.DOTALL)
    assert section_match, "Could not extract Evaluation & Remediation section from skills/signoff/SKILL.md"
    remediation_text = section_match.group(1)

    assert any(term in remediation_text for term in ["not sure", "uncertainty"]), "Missing uncertainty trigger in remediation rule"
    assert "vague" in remediation_text or "hand-waving" in remediation_text, "Missing vague/hand-waving trigger in remediation rule"
    assert "pause signoff" in remediation_text, "Missing 'pause signoff' in remediation rule"
    assert "@skill:explain-diff" in remediation_text, "Missing '@skill:explain-diff' reference in remediation rule"
    assert "re-probe" in remediation_text, "Missing re-probing requirement in remediation rule"

    with open(math_proof_md, "r", encoding="utf-8") as f:
        math_content = f.read()

    assert "Phase 3: Socratic Signoff" in math_content, "Missing Phase 3 in skills/math-proof-audit/SKILL.md"
    assert "@skill:signoff" in math_content, "Missing @skill:signoff reference in math-proof-audit SKILL.md"
    assert "@skill:explain-diff" in math_content, "Missing @skill:explain-diff reference in math-proof-audit SKILL.md"

    # Assert Section 4 Worktree Target Mandate
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

    # GSA v1.0 trailer schema fields
    for trailer in [
        "Signoff-Spec-Version: 1.0",
        "Signoff-Harness-ID",
        "Signoff-Transcript-Bytes",
    ]:
        assert trailer in signoff_content, f"Missing '{trailer}' trailer in skills/signoff/SKILL.md"

    # Portable harness adapter resolution (the core portability goal)
    for adapter_env in [
        "SIGNOFF_TRANSCRIPT_FILE",
        "ANTIGRAVITY_CONVERSATION_ID",
        "CLAUDE_CODE_SESSION_ID",
    ]:
        assert adapter_env in signoff_content, f"Missing '{adapter_env}' adapter resolution in skills/signoff/SKILL.md"

    # Worktree fallback: cwd slug misses inside linked worktrees, so the adapter
    # must resolve the primary repository root via git-common-dir
    assert "--git-common-dir" in signoff_content, "Missing worktree git-common-dir fallback in skills/signoff/SKILL.md"

    # Git Notes dual persistence with tracking-ref concurrency merge
    assert "refs/notes/signoff" in signoff_content, "Missing 'refs/notes/signoff' persistence in skills/signoff/SKILL.md"
    assert "cat_sort_uniq" in signoff_content, "Missing 'cat_sort_uniq' notes merge strategy in skills/signoff/SKILL.md"
    assert "refs/notes/signoff-remote" in signoff_content, "Missing tracking-ref fetch for notes merge in skills/signoff/SKILL.md"

    # Signed attestation commits (GSA spec section 2.4)
    assert "user.signingkey" in signoff_content, "Missing signed-commit support (user.signingkey) in skills/signoff/SKILL.md"

    # Spec cross-reference resolves relative to the skill directory
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
    # Deterministic sources for the priority harness
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

    # Every profile block declares a Profile-ID matching the trailer token grammar
    for block, source in [
        (embedded_block, "skills/signoff/SKILL.md"),
        (science_profile_content, "skills/signoff/profiles/domain-science.md"),
    ]:
        pid = re.search(r"^Profile-ID:\s*([a-z0-9-]+)\s*$", block, re.MULTILINE)
        assert pid, f"Missing or malformed Profile-ID in {source}"
    assert "Profile-ID: software-general" in embedded_block, "Default embedded profile must be software-general"
    assert "Profile-ID: domain-science" in science_profile_content, "domain-science profile must declare its Profile-ID"

    # External-user documentation: the block is the sole customization point
    assert "sole customization point" in signoff_content, "Missing 'sole customization point' marker in skills/signoff/SKILL.md"
    assert "sole customization point" in harnesses_content, "Missing 'sole customization point' documentation in skills/signoff/HARNESSES.md"
    assert "profiles/software-general.md" in harnesses_content, "Missing software-general profile reference in HARNESSES.md"
    assert "profiles/domain-science.md" in harnesses_content, "Missing domain-science profile reference in HARNESSES.md"



