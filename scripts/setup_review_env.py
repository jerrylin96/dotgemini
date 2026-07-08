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
    try:
        import tomli as tomllib
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
    project_sec = re.search(r'^\[project\](.*?)(?=(?:^\s*\[)|\Z)', content, re.DOTALL | re.MULTILINE)
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
    opt_sec = re.search(r'^\[project\.optional-dependencies\](.*?)(?=(?:^\s*\[)|\Z)', content, re.DOTALL | re.MULTILINE)
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

def compute_fingerprint(workspace_path, extra_deps):
    hash_obj = hashlib.sha256()
    # Hash the dependency list representation
    hash_obj.update(repr(extra_deps).encode("utf-8"))
    # Hash contents of config and lock files
    files_to_hash = ["pyproject.toml", "uv.lock", "poetry.lock", "requirements.txt", "setup.py"]
    for filename in files_to_hash:
        file_path = os.path.join(workspace_path, filename)
        if os.path.exists(file_path):
            hash_obj.update(filename.encode("utf-8"))
            try:
                with open(file_path, "rb") as f:
                    hash_obj.update(f.read())
            except Exception:
                pass
    return hash_obj.hexdigest()

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
    pyproject_path = os.path.join(workspace_path, "pyproject.toml")
    uv_lock_path = os.path.join(workspace_path, "uv.lock")
    
    if os.path.exists(venv_python):
        print("Virtual environment already exists.")
    else:
        print("Creating virtual environment...")
        cmd_venv = [uv_bin, "venv", env_path]
        if os.path.exists(pyproject_path):
            try:
                data = load_pyproject(pyproject_path)
                requires_python = data.get("project", {}).get("requires-python")
                if requires_python:
                    print(f"Detected Python requirement: {requires_python}")
                    cmd_venv += ["--python", requires_python]
            except Exception as e:
                print(f"Warning: Could not parse python version from pyproject.toml: {e}")
        subprocess.run(cmd_venv, env={**os.environ, "UV_PROJECT_ENVIRONMENT": env_path}, check=True)

    # 5. Determine dependencies to install
    print("Resolving dependencies...")
    install_deps = ["pytest", "pytest-cov", "black", "ruff"]
    
    if os.path.exists(pyproject_path):
        try:
            data = load_pyproject(pyproject_path)
            project_name = data.get("project", {}).get("name", "unknown")
            print(f"Parsing dependencies for project: {project_name}")
            
            # Extract dependencies
            deps = data.get("project", {}).get("dependencies", [])
            optional_groups = data.get("project", {}).get("optional-dependencies", {})
            
            # Prefer CPU / review-specific optional dependencies if available
            groups_to_include = ["test", "dev", "vis"]
            for group in optional_groups:
                if "cpu" in group.lower() or "review" in group.lower():
                    groups_to_include.append(group)
            
            for group in set(groups_to_include):
                if group in optional_groups:
                    deps.extend(optional_groups[group])
            
            # Filter out GPU-specific / NVIDIA / DALI / macOS-incompatible packages on macOS CPU
            for dep in deps:
                dep_lower = dep.lower()
                is_gpu = any(x in dep_lower for x in ["nvidia", "cuda", "dali", "torch-harmonics", "triton", "tensorrt", "cupy"])
                is_incompatible_platform = False
                if sys.platform == "darwin":
                    if "win-amd64" in dep_lower or "linux-x86_64" in dep_lower:
                        is_incompatible_platform = True
                
                if is_gpu or is_incompatible_platform:
                    print(f" -> Skipping GPU/NVIDIA/Platform-specific dependency: {dep}")
                else:
                    install_deps.append(dep)
        except Exception as e:
            print(f"Warning: Could not parse dependencies from pyproject.toml: {e}")
            
    # De-duplicate dependencies
    install_deps = list(dict.fromkeys(install_deps))
    
    # Check fingerprint to avoid unnecessary reinstalls
    current_fingerprint = compute_fingerprint(workspace_path, install_deps)
    fingerprint_file = os.path.join(env_path, ".deps_fingerprint")
    
    skip_install = False
    if os.path.exists(fingerprint_file):
        try:
            with open(fingerprint_file, "r") as f:
                stored_fingerprint = f.read().strip()
            if stored_fingerprint == current_fingerprint:
                skip_install = True
        except Exception:
            pass
            
    if skip_install:
        print("Dependencies and configuration are unchanged. Skipping installation.")
    else:
        # 6. Install dependencies
        print("Installing / Syncing dependencies...")
        if os.path.exists(uv_lock_path):
            print("Found uv.lock. Synchronizing with 'uv sync'...")
            subprocess.run(
                [uv_bin, "sync"],
                cwd=workspace_path,
                env={**os.environ, "VIRTUAL_ENV": env_path, "UV_PROJECT_ENVIRONMENT": env_path},
                check=True
            )
            # Ensure dev tools are present
            print("Installing review tools...")
            subprocess.run(
                [uv_bin, "pip", "install", "pytest", "pytest-cov", "black", "ruff"],
                env={**os.environ, "VIRTUAL_ENV": env_path, "UV_PROJECT_ENVIRONMENT": env_path},
                check=True
            )
        else:
            print(f"Installing {len(install_deps)} dependencies via 'uv pip install'...")
            cmd_install = [uv_bin, "pip", "install"] + install_deps
            subprocess.run(
                cmd_install,
                env={**os.environ, "VIRTUAL_ENV": env_path, "UV_PROJECT_ENVIRONMENT": env_path},
                check=True
            )
            
        # 7. Install project in editable mode if pyproject.toml exists (and not uv.lock since uv sync does this)
        if os.path.exists(pyproject_path) and not os.path.exists(uv_lock_path):
            print("Installing workspace project in editable mode (no-deps)...")
            subprocess.run(
                [uv_bin, "pip", "install", "--no-deps", "-e", workspace_path],
                env={**os.environ, "VIRTUAL_ENV": env_path, "UV_PROJECT_ENVIRONMENT": env_path},
                check=True
            )
            
        # Save fingerprint
        try:
            with open(fingerprint_file, "w") as f:
                f.write(current_fingerprint)
        except Exception as e:
            print(f"Warning: Could not save dependency fingerprint: {e}")
        
    # Confirm env_path/bin/python and review tools exist and fail clearly if not
    pytest_bin = os.path.join(env_path, "bin", "pytest")
    ruff_bin = os.path.join(env_path, "bin", "ruff")
    
    if not os.path.exists(venv_python):
        print(f"Error: Python executable not found in virtual environment at {venv_python}")
        sys.exit(1)
        
    for tool, tool_path in [("pytest", pytest_bin), ("ruff", ruff_bin)]:
        if not os.path.exists(tool_path):
            print(f"Error: Review tool '{tool}' not found in virtual environment at {tool_path}")
            sys.exit(1)

    print("\n--- Review environment setup complete! ---")
    print(f"Path: {env_path}")
    print(f"To run tests: {os.path.join(env_path, 'bin', 'pytest')}")
    print(f"To run ruff:  {os.path.join(env_path, 'bin', 'ruff')} check .")

if __name__ == "__main__":
    main()
