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

    # Execution safety and handoff rule assertions
    assert "Single Active Writer" in inc_content, "Missing Single Active Writer rule in incremental-implementation"
    assert "Pre-Dispatch Verification Gate" in inc_content, "Missing Pre-Dispatch Verification Gate in incremental-implementation"
    assert "Failure Circuit Breaker" in inc_content, "Missing Failure Circuit Breaker in incremental-implementation"
    assert "git add -- <intended-paths>" in inc_content, "Missing safe path-specific staging instruction in incremental-implementation"
    assert "parent conversation ID" in inc_content, "Missing explicit parent conversation ID scratchpad reference in incremental-implementation"

    # Strategy selection checkbox assertion
    assert "ensuring exactly one strategy checkbox is selected" in plan_content, "Missing single strategy checkbox assertion in planning-and-task-breakdown"
