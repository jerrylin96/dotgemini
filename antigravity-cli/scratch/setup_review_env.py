#!/usr/bin/env python3
import sys
import os
import hashlib
import subprocess
import shutil
import re

# Fallback for Python 3.10 which lacks tomllib
try:
    import tomllib
    HAS_TOMLLIB = True
except ImportError:
    HAS_TOMLLIB = False

def fallback_parse_toml(filepath):
    """
    ponytail: Regex-based fallback TOML parser for Python 3.10 compatibility.
    Only extracts fields needed by this script.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return {}
    
    # Strip comments
    content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
    result = {}
    
    # Extract project section
    project_sec = re.search(r'\[project\](.*?)(?:\[|$)', content, re.DOTALL)
    if project_sec:
        project_text = project_sec.group(1)
        name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', project_text)
        if name_match:
            result.setdefault("project", {})["name"] = name_match.group(1)
            
        req_match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', project_text)
        if req_match:
            result.setdefault("project", {})["requires-python"] = req_match.group(1)
            
        deps_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', project_text, re.DOTALL)
        if deps_match:
            deps_text = deps_match.group(1)
            deps = re.findall(r'["\']([^"\']+)["\']', deps_text)
            result.setdefault("project", {})["dependencies"] = deps
            
    # Extract optional-dependencies
    opt_sec = re.search(r'\[project\.optional-dependencies\](.*?)(?:\[|$)', content, re.DOTALL)
    if opt_sec:
        opt_text = opt_sec.group(1)
        groups = re.findall(r'(\w+)\s*=\s*\[(.*?)\]', opt_text, re.DOTALL)
        opt_deps = {}
        for group_name, group_deps_text in groups:
            deps = re.findall(r'["\']([^"\']+)["\']', group_deps_text)
            opt_deps[group_name] = deps
        result.setdefault("project", {})["optional-dependencies"] = opt_deps
        
    return result

def load_pyproject(filepath):
    if HAS_TOMLLIB:
        try:
            with open(filepath, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            print(f"Warning: tomllib failed parsing {filepath}: {e}. Retrying with regex...")
    return fallback_parse_toml(filepath)

def main():
    # 1. Determine active workspace
    if len(sys.argv) > 1:
        workspace_path = os.path.abspath(sys.argv[1])
    else:
        workspace_path = os.getcwd()
        
    print("--- Antigravity Dynamic Review Env Manager ---")
    print(f"Active workspace: {workspace_path}")
    
    # 2. Calculate dynamic env path based on workspace path hash
    path_hash = hashlib.md5(workspace_path.encode('utf-8')).hexdigest()
    env_name = path_hash
    
    envs_root = os.path.expanduser("~/.gemini/tmp")
    os.makedirs(envs_root, exist_ok=True)
    env_path = os.path.join(envs_root, env_name)
    
    print(f"Target env: {env_path}")
    
    # 3. Locate uv executable
    uv_bin = os.path.expanduser("~/.local/bin/uv")
    if not os.path.exists(uv_bin):
        uv_bin = shutil.which("uv")
        if not uv_bin:
            print("Error: 'uv' executable not found in PATH or ~/.local/bin/uv.")
            sys.exit(1)
            
    # 4. Initialize virtual environment if it doesn't exist
    venv_python = os.path.join(env_path, "bin", "python")
    if os.path.exists(venv_python):
        print("Virtual environment already exists.")
    else:
        print("Creating virtual environment...")
        # Check Python requirement in pyproject.toml if available
        pyproject_path = os.path.join(workspace_path, "pyproject.toml")
        cmd_venv = [uv_bin, "venv", env_path]
        if os.path.exists(pyproject_path):
            try:
                data = load_pyproject(pyproject_path)
                requires_python = data.get("project", {}).get("requires-python", ">=3.10")
                print(f"Detected Python requirement: {requires_python}")
                
                # Safer check for 3.10 targeting
                versions = re.findall(r'3\.\d+', requires_python)
                if versions and versions[0] == "3.10":
                    cmd_venv += ["--python", "3.10"]
            except Exception as e:
                print(f"Warning: Could not parse python version from pyproject.toml: {e}")
        subprocess.run(cmd_venv, check=True)

    # 5. Determine dependencies to install
    print("Resolving dependencies...")
    install_deps = ["pytest", "pytest-cov", "black", "ruff"]
    
    pyproject_path = os.path.join(workspace_path, "pyproject.toml")
    if os.path.exists(pyproject_path):
        try:
            data = load_pyproject(pyproject_path)
            project_name = data.get("project", {}).get("name", "unknown")
            print(f"Parsing dependencies for project: {project_name}")
            
            # Extract dependencies
            deps = data.get("project", {}).get("dependencies", [])
            optional_groups = data.get("project", {}).get("optional-dependencies", {})
            for group, group_deps in optional_groups.items():
                if group in ["test", "dev", "vis"]:
                    deps.extend(group_deps)
            
            # Filter out GPU-specific / NVIDIA / DALI / macOS-incompatible packages on macOS CPU
            for dep in deps:
                dep_lower = dep.lower()
                if "nvidia" in dep_lower or "cuda" in dep_lower or "dali" in dep_lower or "torch-harmonics" in dep_lower:
                    print(f" -> Skipping GPU/NVIDIA/Platform-specific dependency: {dep}")
                else:
                    install_deps.append(dep)
        except Exception as e:
            print(f"Warning: Could not parse dependencies from pyproject.toml: {e}")
            
    # De-duplicate dependencies
    install_deps = list(dict.fromkeys(install_deps))
    
    # 6. Install dependencies
    print(f"Installing {len(install_deps)} dependencies...")
    cmd_install = [uv_bin, "pip", "install"] + install_deps
    subprocess.run(cmd_install, env={**os.environ, "VIRTUAL_ENV": env_path}, check=True)
    
    # 7. Install project in editable mode if pyproject.toml exists
    if os.path.exists(pyproject_path):
        print("Installing workspace project in editable mode (no-deps)...")
        subprocess.run([uv_bin, "pip", "install", "--no-deps", "-e", workspace_path], env={**os.environ, "VIRTUAL_ENV": env_path}, check=True)
        
    print("\n--- Review environment setup complete! ---")
    print(f"Path: {env_path}")
    print(f"To run tests: {os.path.join(env_path, 'bin', 'pytest')}")
    print(f"To run ruff:  {os.path.join(env_path, 'bin', 'ruff')} check .")

if __name__ == "__main__":
    main()
