#!/usr/bin/env python3
import sys
import os
import subprocess
import hashlib
import shutil

def main():
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    setup_script = os.path.join(workspace_root, "scripts", "setup_review_env.py")
    
    uv_bin = os.path.expanduser("~/.local/bin/uv")
    has_uv = os.path.exists(uv_bin) or (shutil.which("uv") is not None)
    
    setup_success = False
    if has_uv:
        print(f"Ensuring test environment is set up via {setup_script}...", flush=True)
        try:
            subprocess.run([sys.executable, setup_script, workspace_root], check=True)
            setup_success = True
        except subprocess.CalledProcessError as e:
            if os.environ.get("ALLOW_HOST_TEST_FALLBACK") == "1":
                print(f"Warning: test environment setup failed: {e}. ALLOW_HOST_TEST_FALLBACK=1 is set, falling back to host environment.", file=sys.stderr, flush=True)
            else:
                print(f"Error: test environment setup failed: {e}. To fall back to host testing, run with ALLOW_HOST_TEST_FALLBACK=1.", file=sys.stderr, flush=True)
                sys.exit(e.returncode)
    else:
        print("uv is not available. Skipping setup_review_env.py and falling back to host environment.", flush=True)
        
    path_hash = hashlib.sha256(workspace_root.encode('utf-8')).hexdigest()[:16]
    pytest_bin = os.path.expanduser(f"~/.gemini/tmp/{path_hash}/bin/pytest")
    
    if setup_success and os.path.exists(pytest_bin):
        cmd = [pytest_bin, "--import-mode=importlib"] + sys.argv[1:]
        print(f"Running tests via venv: {' '.join(cmd)}", flush=True)
        result = subprocess.run(cmd, cwd=workspace_root)
        sys.exit(result.returncode)
    else:
        print("Falling back to host environment testing...", flush=True)
        try:
            import pytest  # noqa: F401
            has_pytest = True
        except ImportError:
            has_pytest = False
            
        if has_pytest:
            cmd = [sys.executable, "-m", "pytest", "--import-mode=importlib"] + sys.argv[1:]
            print(f"Running host pytest: {' '.join(cmd)}", flush=True)
            result = subprocess.run(cmd, cwd=workspace_root)
            sys.exit(result.returncode)
        else:
            print("pytest not found on host. Running host unittest...", flush=True)
            test_dirs = ["scripts/tests"]
            skills_root = os.path.join(workspace_root, "skills")
            if os.path.isdir(skills_root):
                for name in sorted(os.listdir(skills_root)):
                    tests_dir = os.path.join(skills_root, name, "tests")
                    if os.path.isdir(tests_dir):
                        test_dirs.append(f"skills/{name}/tests")
            exit_code = 0
            for d in test_dirs:
                if os.path.exists(os.path.join(workspace_root, d)):
                    cmd = [sys.executable, "-m", "unittest", "discover", "-s", d, "-p", "test_*.py"]
                    print(f"Running: {' '.join(cmd)}", flush=True)
                    res = subprocess.run(cmd, cwd=workspace_root)
                    if res.returncode != 0:
                        exit_code = res.returncode
            sys.exit(exit_code)

if __name__ == "__main__":
    main()
