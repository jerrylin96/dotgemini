import glob
import os
import re

def test_all_skill_references_resolve():
    """Verify that every @skill:<name> reference in skills/ matches an existing skill folder."""
    # Find all skill names
    skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../skills"))
    existing_skills = {
        name for name in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, name))
    }
    
    # Regex to find @skill:<name> (handling markdown bold formatting around it if any)
    # E.g., @skill:managing-python-dependencies or **@skill:bigquery**
    skill_ref_pattern = re.compile(r"@skill:([a-zA-Z0-9_-]+)")
    
    errors = []
    # Scan all markdown files in skills/ recursively
    markdown_files = glob.glob(os.path.join(skills_dir, "**/*.md"), recursive=True)
    for filepath in markdown_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        matches = skill_ref_pattern.findall(content)
        for ref in matches:
            # Check if skill directory exists
            if ref not in existing_skills:
                rel_path = os.path.relpath(filepath, skills_dir)
                errors.append(f"In {rel_path}: reference '@skill:{ref}' does not match any folder in skills/")
                
    assert not errors, "\n".join(errors)
