import glob
import os
import re

def parse_frontmatter_name(skill_md_path):
    """Parse name from YAML frontmatter without external YAML parser dependency."""
    if not os.path.exists(skill_md_path):
        return None
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Find YAML block
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    frontmatter = parts[1]
    match = re.search(r"^name:\s*([a-zA-Z0-9_-]+)", frontmatter, re.MULTILINE)
    return match.group(1) if match else None

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
    """Verify that no markdown file contains absolute developer-specific file:// URLs (e.g. referencing home or worktree)."""
    skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../skills"))
    
    # Matches markdown link target starting with file://
    file_link_pattern = re.compile(r"\]\((file://[^\)]+)\)")
    
    non_portable_patterns = [
        re.compile(r"file:///(Users|home|tmp|private|var|worktrees)/"),
        re.compile(r"gemini_remove-bq-bloat"),
    ]
    
    errors = []
    markdown_files = glob.glob(os.path.join(skills_dir, "**/*.md"), recursive=True)
    for filepath in markdown_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        links = file_link_pattern.findall(content)
        for link in links:
            for pattern in non_portable_patterns:
                if pattern.search(link):
                    rel_path = os.path.relpath(filepath, skills_dir)
                    errors.append(f"In {rel_path}: non-portable file:// link found: '{link}'")
                    break
                    
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
