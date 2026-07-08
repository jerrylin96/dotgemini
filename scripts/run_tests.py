#!/usr/bin/env python3
import sys
import os
import subprocess
import hashlib

def main():
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    setup_script = os.path.join(workspace_root, "scripts", "setup_review_env.py")
    print(f"Ensuring test environment is set up via {setup_script}...")
    try:
        subprocess.run([sys.executable, setup_script, workspace_root], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: test environment setup failed: {e}", file=sys.stderr)
        sys.exit(1)
        
    path_hash = hashlib.md5(workspace_root.encode('utf-8')).hexdigest()
    pytest_bin = os.path.expanduser(f"~/.gemini/tmp/{path_hash}/bin/pytest")
    
    if not os.path.exists(pytest_bin):
        print(f"Error: pytest binary not found at {pytest_bin}", file=sys.stderr)
        sys.exit(1)
        
    cmd = [pytest_bin, "--import-mode=importlib"] + sys.argv[1:]
    print(f"Running tests: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=workspace_root)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
