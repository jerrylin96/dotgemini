#!/usr/bin/env python3
import sys
import os
import subprocess
import hashlib

def main():
    if len(sys.argv) < 3:
        print("Usage: run_in_env.py <workspace_path> <command> [args...]")
        sys.exit(1)
        
    workspace_path = os.path.abspath(sys.argv[1])
    cmd = sys.argv[2]
    cmd_args = sys.argv[3:]
    
    path_hash = hashlib.sha256(workspace_path.encode('utf-8')).hexdigest()
    env_bin_dir = os.path.expanduser(f"~/.gemini/tmp/{path_hash}/bin")
    
    executable = os.path.join(env_bin_dir, cmd)
    if not os.path.exists(executable):
        print(f"Error: Executable '{cmd}' not found in env at {env_bin_dir}. Run setup_review_env.py first.")
        sys.exit(1)
        
    full_cmd = [executable] + cmd_args
    
    # Set up environment variables to mimic active venv
    env = os.environ.copy()
    env["PATH"] = f"{env_bin_dir}{os.path.pathsep}{env.get('PATH', '')}"
    env["VIRTUAL_ENV"] = os.path.dirname(env_bin_dir)
    
    # Run from the workspace path
    result = subprocess.run(full_cmd, env=env, cwd=workspace_path)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
