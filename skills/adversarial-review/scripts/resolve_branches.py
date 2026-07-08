#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import shutil
import hashlib

# Try importing fcntl for flock on Unix platforms (macOS/Linux)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

class FileLock:
    def __init__(self, lock_path):
        self.lock_path = lock_path
        self.lock_file = None

    def __enter__(self):
        if not HAS_FCNTL:
            return self
        try:
            self.lock_file = open(self.lock_path, "w")
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.stderr.write("Another instance is running. Waiting for lock...\n")
            fcntl.flock(self.lock_file, fcntl.LOCK_EX)
        except Exception as e:
            sys.stderr.write(f"Warning: could not acquire lock: {str(e)}\n")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if HAS_FCNTL and self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
                self.lock_file.close()
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
            except Exception:
                pass

def run_git(args, cwd=None, timeout=60):
    # Setup environment to prevent blocking on interactive prompts
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=env
        )
    except subprocess.TimeoutExpired:
        raise Exception(f"Git command timed out after {timeout} seconds: git {' '.join(args)}")
        
    if result.returncode != 0:
        raise Exception(f"Git command failed: git {' '.join(args)}\nError: {result.stderr.strip()}")
    return result.stdout.strip()

def get_current_branch(cwd):
    # First try symbolic-ref
    try:
        branch = run_git(["symbolic-ref", "--short", "HEAD"], cwd=cwd)
        if branch:
            return branch
    except Exception:
        pass
    
    # Fall back to branch --show-current
    try:
        branch = run_git(["branch", "--show-current"], cwd=cwd)
        if branch:
            return branch
    except Exception:
        pass
        
    # Detached HEAD: Fallback to current commit hash
    try:
        commit_hash = run_git(["rev-parse", "--short", "HEAD"], cwd=cwd)
        if commit_hash:
            return commit_hash
    except Exception:
        pass
        
    return "HEAD"

def fetch_all(cwd):
    try:
        # Fetch silently with timeout to prevent hanging
        run_git(["fetch", "--all", "--prune"], cwd=cwd, timeout=30)
    except Exception as e:
        # Ignore fetch errors if offline, but log
        sys.stderr.write(f"Warning: git fetch failed: {str(e)}\n")

def get_remotes(cwd):
    """Retrieve the list of registered remote names."""
    try:
        out = run_git(["remote"], cwd=cwd)
        return [line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        return ["origin"]  # Fallback to origin if remote query fails

def get_recent_branches(cwd, ref_branch):
    # Get active remotes to dynamically identify remote tracking prefixes
    remotes = get_remotes(cwd)
    # Sort remotes longest-first to prevent prefix collision (e.g. origin-fork vs origin)
    remotes.sort(key=len, reverse=True)
    
    # Get branches sorted by committer date
    # Format: %(refname:short)|%(committerdate:unix)|%(objectname)|%(subject)
    fmt = "%(refname:short)|%(committerdate:unix)|%(objectname)|%(subject)"
    out = run_git(["for-each-ref", "--sort=-committerdate", f"--format={fmt}", "refs/heads/", "refs/remotes/"], cwd=cwd)
    
    branches = []
    seen_branches = set()
    
    # Generate exclusion prefixes based on current branch
    exclude_prefixes = [
        ref_branch,
        "HEAD",
    ]
    for remote in remotes:
        exclude_prefixes.append(f"{remote}/{ref_branch}")
        exclude_prefixes.append(f"remotes/{remote}/{ref_branch}")
        exclude_prefixes.append(f"{remote}/HEAD")
        exclude_prefixes.append(f"remotes/{remote}/HEAD")
    
    exclude_prefixes_set = set(exclude_prefixes)
    
    for line in out.splitlines():
        if not line:
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        name, timestamp_str, commit_hash, subject = parts
        
        # Clean branch name by removing remote prefixes dynamically
        clean_name = name
        for remote in remotes:
            if clean_name.startswith(f"{remote}/"):
                clean_name = clean_name[len(f"{remote}/"):]
                break
            elif clean_name.startswith(f"remotes/{remote}/"):
                clean_name = clean_name[len(f"remotes/{remote}/"):]
                break
            
        if (clean_name in exclude_prefixes_set or 
            name in exclude_prefixes_set or 
            name in remotes or 
            name.endswith("/HEAD") or 
            clean_name == "HEAD"):
            continue
            
        if clean_name in seen_branches:
            continue
            
        seen_branches.add(clean_name)
        
        try:
            timestamp = int(timestamp_str)
        except ValueError:
            timestamp = 0
            
        branches.append({
            "full_name": name,
            "branch_name": clean_name,
            "timestamp": timestamp,
            "commit_hash": commit_hash,
            "subject": subject
        })
        
    return branches

def get_worktree_map(cwd):
    """Retrieve all active worktrees using git worktree list --porcelain."""
    try:
        out = run_git(["worktree", "list", "--porcelain"], cwd=cwd)
    except Exception as e:
        sys.stderr.write(f"Warning: failed to list worktrees: {str(e)}\n")
        return []
        
    worktrees = []
    current_wt = {}
    for line in out.splitlines():
        if not line:
            if current_wt:
                worktrees.append(current_wt)
                current_wt = {}
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2:
            key, val = parts
            if key == "worktree":
                current_wt["path"] = os.path.abspath(val)
            elif key == "branch":
                ref = val
                if ref.startswith("refs/heads/"):
                    ref = ref[len("refs/heads/"):]
                current_wt["branch"] = ref
    if current_wt:
        worktrees.append(current_wt)
    return worktrees

def parse_remote_ref(remote_ref, remotes):
    """Cleans a remote ref name and returns the remote name and the resolved remote ref."""
    ref = remote_ref
    # Remove common prefixes
    for prefix in ["refs/remotes/", "remotes/"]:
        if ref.startswith(prefix):
            ref = ref[len(prefix):]
            
    # Find matching remote prefix
    for remote in remotes:
        if ref.startswith(f"{remote}/"):
            return remote, ref
            
    return "origin", ref

def setup_worktree(cwd, branch_name, remote_ref=None):
    # Absolute paths to prevent directory traversal
    cwd_abs = os.path.abspath(cwd)
    
    # Generate a unique hash for this repository to prevent collisions with other repos
    repo_hash = hashlib.sha256(cwd_abs.encode("utf-8")).hexdigest()[:8]
    
    # Clean and sanitize the branch name to prevent path traversal
    safe_folder = branch_name.replace("/", "_").replace("\\", "_")
    # Strip any potential relative traversal pieces
    safe_folder = "".join(c for c in safe_folder if c.isalnum() or c in ("-", "_", "."))
    
    if not safe_folder or safe_folder in (".", ".."):
        raise ValueError(f"Unsafe branch name: {branch_name}")
        
    wt_root = os.path.expanduser("~/.gemini/tmp/worktrees")
    os.makedirs(wt_root, exist_ok=True)
    wt_root_abs = os.path.abspath(wt_root)
    
    # Target path containing repo hash to isolate worktrees per repository
    target_path = os.path.abspath(os.path.join(wt_root_abs, f"{repo_hash}_{safe_folder}"))
    
    # Ensure target_path is strictly inside wt_root_abs (Defense in Depth)
    if not target_path.startswith(wt_root_abs + os.sep) and target_path != wt_root_abs:
        raise ValueError("Path traversal attempt detected in worktree setup.")
    
    # Find active worktrees for the current repository
    wt_list = get_worktree_map(cwd_abs)
    
    wt_path = None
    for wt in wt_list:
        if wt.get("branch") == branch_name:
            wt_path = wt.get("path")
            break
            
    # Get active remotes
    remotes = get_remotes(cwd_abs)

    if wt_path:
        # Worktree already exists and is active for this repository
        sys.stderr.write(f"Worktree for {branch_name} exists at {wt_path}. Updating...\n")
        # Ensure clean state as requested (adversarial reviews should always be clean)
        # ponytail: discarding uncommitted changes is required by the user rules here
        run_git(["reset", "--hard"], cwd=wt_path)
        # Pull or reset to remote tracking branch if remote is specified
        if remote_ref:
            remote_name, resolved_ref = parse_remote_ref(remote_ref, remotes)
            try:
                run_git(["fetch", remote_name], cwd=wt_path)
                run_git(["reset", "--hard", "--", resolved_ref], cwd=wt_path)
            except Exception as e:
                sys.stderr.write(f"Warning: failed to reset to remote {resolved_ref}: {str(e)}\n")
        else:
            try:
                run_git(["pull"], cwd=wt_path)
            except Exception as e:
                sys.stderr.write(f"Warning: pull failed: {str(e)}\n")
        return wt_path
        
    # If path directory exists on disk but is NOT registered as a worktree for this repo, clean it up
    if os.path.exists(target_path):
        sys.stderr.write(f"Stale directory found at {target_path}. Cleaning...\n")
        shutil.rmtree(target_path, ignore_errors=True)
        # Remove registered but missing worktrees
        try:
            run_git(["worktree", "prune"], cwd=cwd_abs)
        except Exception:
            pass
            
    # Create worktree
    sys.stderr.write(f"Creating new worktree for {branch_name} at {target_path}...\n")
    
    # If remote_ref exists and differs from local branch, check if local branch exists
    if remote_ref:
        try:
            # Safer, non-scraping check for local branch existence
            run_git(["show-ref", "--verify", f"refs/heads/{branch_name}"], cwd=cwd_abs)
            local_exists = True
        except Exception:
            local_exists = False
            
        if not local_exists:
            # Create local branch tracking remote branch (use '--' separator to avoid option injection)
            run_git(["branch", "--track", "--", branch_name, remote_ref], cwd=cwd_abs)
            
    # Add the worktree safely using '--' to prevent option injection
    run_git(["worktree", "add", target_path, "--", branch_name], cwd=cwd_abs)
    
    # Ensure clean reset to match remote if remote_ref is given
    if remote_ref:
        remote_name, resolved_ref = parse_remote_ref(remote_ref, remotes)
        try:
            run_git(["reset", "--hard", "--", resolved_ref], cwd=target_path)
        except Exception as e:
            sys.stderr.write(f"Warning: failed to reset new worktree to remote {resolved_ref}: {str(e)}\n")
            
    return target_path

def main():
    cwd = os.getcwd()
    if not os.path.exists(os.path.join(cwd, ".git")):
        print(json.dumps({"error": "Current directory is not a Git repository root."}))
        sys.exit(1)
        
    # Handle explicit prune command
    if len(sys.argv) > 1 and sys.argv[1] == "--prune":
        wt_root = os.path.expanduser("~/.gemini/tmp/worktrees")
        if os.path.exists(wt_root):
            sys.stderr.write(f"Cleaning worktree directory {wt_root}...\n")
            shutil.rmtree(wt_root, ignore_errors=True)
        # Prune git registration
        try:
            run_git(["worktree", "prune"], cwd=cwd)
        except Exception as e:
            sys.stderr.write(f"Warning: git worktree prune failed: {str(e)}\n")
        print(json.dumps({"success": True, "message": "Worktree cache pruned successfully."}))
        sys.exit(0)

    # Use a lock file to prevent race conditions during concurrent runs
    wt_root = os.path.expanduser("~/.gemini/tmp/worktrees")
    os.makedirs(wt_root, exist_ok=True)
    lock_path = os.path.join(wt_root, "resolve_branches.lock")
    
    with FileLock(lock_path):
        try:
            ref_branch = get_current_branch(cwd)
            fetch_all(cwd)
            branches = get_recent_branches(cwd, ref_branch)
            
            if not branches:
                print(json.dumps({
                    "reference_branch": ref_branch,
                    "feature_branch": None,
                    "ambiguous": False,
                    "candidates": [],
                    "message": "No other branches found to compare."
                }))
                sys.exit(0)
                
            # Determine ambiguity.
            # If the top branch's timestamp is very close to others, say within 10 minutes (600s),
            # flag it as ambiguous if there are multiple branches.
            ambiguous = False
            candidates = branches[:5]  # top 5 recent branches
            
            if len(candidates) > 1:
                time_diff = candidates[0]["timestamp"] - candidates[1]["timestamp"]
                if time_diff <= 600:
                    ambiguous = True
                    
            # If user passed a specific branch target, we resolve that one directly
            selected_branch = None
            if len(sys.argv) > 1:
                target_input = sys.argv[1]
                # Match against candidates
                for cand in branches:
                    if cand["branch_name"] == target_input or cand["full_name"] == target_input:
                        selected_branch = cand
                        ambiguous = False
                        break
                if not selected_branch:
                    print(json.dumps({"error": f"Branch '{target_input}' not found."}))
                    sys.exit(1)
            else:
                selected_branch = candidates[0]
                
            # If ambiguous and no explicit branch requested, let agent know so it can ask user
            if ambiguous and len(sys.argv) == 1:
                print(json.dumps({
                    "reference_branch": ref_branch,
                    "feature_branch": None,
                    "ambiguous": True,
                    "candidates": candidates
                }, indent=2))
                sys.exit(0)
                
            # Setup/Update worktree
            remote_ref = None
            remotes = get_remotes(cwd)
            for cand in branches:
                if cand["branch_name"] == selected_branch["branch_name"]:
                    # Check starts with any remote name
                    is_remote = False
                    for remote in remotes:
                        if cand["full_name"].startswith(f"{remote}/") or cand["full_name"].startswith(f"remotes/{remote}/"):
                            is_remote = True
                            break
                    if is_remote:
                        remote_ref = cand["full_name"]
                        break
                        
            wt_path = setup_worktree(cwd, selected_branch["branch_name"], remote_ref)
            
            print(json.dumps({
                "reference_branch": ref_branch,
                "feature_branch": selected_branch["branch_name"],
                "ambiguous": False,
                "worktree_path": wt_path,
                "commit_hash": selected_branch["commit_hash"],
                "subject": selected_branch["subject"]
            }, indent=2))
            
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)

if __name__ == "__main__":
    main()
