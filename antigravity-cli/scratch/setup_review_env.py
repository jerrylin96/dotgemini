#!/usr/bin/env python3
import sys
import os
import hashlib
import subprocess
import shutil
import tomllib

def main():
    # 1. Determine active workspace
    if len(sys.argv) > 1:
        workspace_path = os.path.abspath(sys.argv[1])
    else:
        workspace_path = os.getcwd()
        
    print(f"--- Antigravity Dynamic Review Env Manager ---")
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
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                requires_python = data.get("project", {}).get("requires-python", ">=3.10")
                print(f"Detected Python requirement: {requires_python}")
                if "3.10" in requires_python or ">=3.10" in requires_python:
                    cmd_venv += ["--python", "3.10"]
            except Exception as e:
                print(f"Warning: Could not parse python version from pyproject.toml: {e}")
        subprocess.run(cmd_venv, check=True)

    # 5. Determine dependencies to install
    print("Resolving dependencies...")
    install_deps = ["pytest", "pytest-cov", "black", "ruff", "parameterized", "properscoring"]
    
    pyproject_path = os.path.join(workspace_path, "pyproject.toml")
    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            
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
    
    # 6b. Install specialized dependencies from GitHub if makani
    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            project_name = data.get("project", {}).get("name", "unknown")
            if project_name == "makani":
                print("Detected makani. Installing specialized dependencies from GitHub...")
                print(" -> Installing physicsnemo...")
                subprocess.run([uv_bin, "pip", "install", "git+https://github.com/NVIDIA/physicsnemo.git@v1.3.0"], env={**os.environ, "VIRTUAL_ENV": env_path}, check=True)
                print(" -> Installing torch-harmonics...")
                subprocess.run([uv_bin, "pip", "install", "git+https://github.com/NVIDIA/torch-harmonics.git", "--no-build-isolation"], env={**os.environ, "VIRTUAL_ENV": env_path}, check=True)
        except Exception as e:
            print(f"Warning: Could not install specialized dependencies: {e}")
    
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
