#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import shutil
import hashlib
import time

# Try importing fcntl for flock on Unix platforms (macOS/Linux)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# The time window (in seconds) within which multiple active branches are considered ambiguous.
# 10 minutes (600 seconds) is a reasonable default for concurrent developer activity.
AMBIGUITY_WINDOW_SECS = 600

# Git command timeout (in seconds) used across fetches and other git actions.
GIT_TIMEOUT = 30

class GitError(Exception):
    """Custom exception raised when a Git command fails or times out."""
    pass

class FileLock:
    def __init__(self, lock_path):
        self.lock_path = lock_path
        self.lock_file = None

    def __enter__(self):
        # Open the file; if it fails, raise to the caller.
        self.lock_file = open(self.lock_path, "w")
        
        start_time = time.time()
        timeout = 120
        acquired = False
        
        # Try non-blocking acquisition first
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except (BlockingIOError, OSError):
            sys.stderr.write("Another instance is running. Waiting for lock...\n")
            
        while not acquired:
            if time.time() - start_time > timeout:
                raise TimeoutError("Timed out waiting for file lock after 120 seconds.")
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (BlockingIOError, OSError):
                time.sleep(0.5)
                
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self.lock_file.close()
            except Exception:
                pass

def run_git(args, cwd=None, timeout=GIT_TIMEOUT):
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
        raise GitError(f"Git command timed out after {timeout} seconds: git {' '.join(args)}")
        
    if result.returncode != 0:
        raise GitError(f"Git command failed: git {' '.join(args)}\nError: {result.stderr.strip()}")
    return result.stdout.strip()

def get_current_branch(cwd):
    # First try symbolic-ref
    try:
        branch = run_git(["symbolic-ref", "--short", "HEAD"], cwd=cwd)
        if branch:
            return branch
    except GitError:
        pass
    
    # Fall back to branch --show-current
    try:
        branch = run_git(["branch", "--show-current"], cwd=cwd)
        if branch:
            return branch
    except GitError:
        pass
        
    # Detached HEAD: Fallback to current commit hash
    try:
        commit_hash = run_git(["rev-parse", "--short", "HEAD"], cwd=cwd)
        if commit_hash:
            return commit_hash
    except GitError:
        pass
        
    return "HEAD"

def resolve_integration_branch(cwd):
    # 1. symref refs/remotes/origin/HEAD
    try:
        symref = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=cwd)
        # symref is e.g. "refs/remotes/origin/main"
        if symref.startswith("refs/remotes/"):
            parts = symref[len("refs/remotes/"):].split("/", 1)
            if len(parts) == 2:
                return parts[1]
    except GitError:
        pass

    # 2. local main
    try:
        run_git(["show-ref", "--verify", "refs/heads/main"], cwd=cwd)
        return "main"
    except GitError:
        pass

    # 3. local master
    try:
        run_git(["show-ref", "--verify", "refs/heads/master"], cwd=cwd)
        return "master"
    except GitError:
        pass

    # 4. local develop
    try:
        run_git(["show-ref", "--verify", "refs/heads/develop"], cwd=cwd)
        return "develop"
    except GitError:
        pass

    # 5. current branch as last resort
    return get_current_branch(cwd)

def fetch_all(cwd):
    try:
        # Fetch silently with timeout to prevent hanging
        run_git(["fetch", "--all", "--prune"], cwd=cwd, timeout=GIT_TIMEOUT)
    except GitError as e:
        # Ignore fetch errors if offline, but log
        sys.stderr.write(f"Warning: git fetch failed: {str(e)}\n")

def get_remotes(cwd):
    """Retrieve the list of registered remote names."""
    try:
        out = run_git(["remote"], cwd=cwd)
        list_remotes = [line.strip() for line in out.splitlines() if line.strip()]
        return list_remotes if list_remotes else ["origin"]
    except GitError:
        return ["origin"]  # Fallback to origin if remote query fails

def get_recent_branches(cwd, ref_branch):
    # Get active remotes to dynamically identify remote tracking prefixes
    remotes = get_remotes(cwd)
    # Sort remotes longest-first to prevent prefix collision (e.g. origin-fork vs origin)
    remotes.sort(key=len, reverse=True)
    
    # Get branches sorted by committer date
    # Format: %(refname)|%(committerdate:unix)|%(objectname)|%(subject)
    fmt = "%(refname)|%(committerdate:unix)|%(objectname)|%(subject)"
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
        refname, timestamp_str, commit_hash, subject = parts
        
        if refname.endswith("/HEAD"):
            continue
            
        # Parse short name
        if refname.startswith("refs/heads/"):
            name = refname[len("refs/heads/"):]
        elif refname.startswith("refs/remotes/"):
            name = refname[len("refs/remotes/"):]
        else:
            name = refname
            
        # Clean branch name by removing remote prefixes dynamically
        clean_name = name
        for remote in remotes:
            if clean_name.startswith(f"{remote}/"):
                clean_name = clean_name[len(f"{remote}/"):]
                break
            
        if (clean_name in exclude_prefixes_set or 
            name in exclude_prefixes_set or 
            name in remotes or 
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
    except GitError as e:
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
                # Strip refs/heads/ prefix if present; leave other refs unmodified.
                # Note: detached-HEAD worktrees emit 'HEAD <sha>' and do not hit this branch.
                if ref.startswith("refs/heads/"):
                    ref = ref[len("refs/heads/"):]
                current_wt["branch"] = ref
    if current_wt:
        worktrees.append(current_wt)
    return worktrees

def parse_remote_ref(remote_ref, remotes):
    """Cleans a remote ref name and returns (remote_name, remote_qualified_shortname)."""
    full_remote_ref = remote_ref
    # Remove common prefixes
    for prefix in ["refs/remotes/", "remotes/"]:
        if full_remote_ref.startswith(prefix):
            full_remote_ref = full_remote_ref[len(prefix):]
            break
            
    # Find matching remote prefix
    for remote in remotes:
        if full_remote_ref.startswith(f"{remote}/"):
            return remote, full_remote_ref
            
    return "origin", full_remote_ref

def setup_worktree(cwd, branch_name, remote_ref=None):
    # Absolute paths to prevent directory traversal
    cwd_abs = os.path.abspath(cwd)
    
    # Generate a unique hash for this repository to prevent collisions with other repos
    repo_hash = hashlib.sha256(cwd_abs.encode("utf-8")).hexdigest()[:8]
    
    # Clean and sanitize the branch name to prevent path traversal
    clean_folder = branch_name.replace("/", "_").replace("\\", "_")
    # Strip any potential relative traversal pieces
    clean_folder = "".join(c for c in clean_folder if c.isalnum() or c in ("-", "_", "."))
    
    branch_hash = hashlib.sha256(branch_name.encode("utf-8")).hexdigest()[:6]
    safe_folder = f"{clean_folder}_{branch_hash}"
    
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
        
        # Stash any dirty changes to prevent data loss
        try:
            stash_out = run_git(["stash", "push", "-u", "-m", "adversarial-review auto-stash"], cwd=wt_path)
            if "No local changes to save" not in stash_out:
                sys.stderr.write(f"Stashed existing worktree changes: {stash_out.strip()}\n")
        except GitError as e:
            sys.stderr.write(f"Warning: git stash failed: {str(e)}\n")
            
        # Pull or reset to remote tracking branch if remote is specified
        if remote_ref:
            remote_name, full_remote_ref = parse_remote_ref(remote_ref, remotes)
            try:
                run_git(["fetch", remote_name], cwd=wt_path, timeout=GIT_TIMEOUT)
                # No `--` separator: `git reset` treats `--` as the commit/pathspec split,
                # which would silently turn this into a no-op path reset.
                run_git(["reset", full_remote_ref], cwd=wt_path)
            except GitError as e:
                sys.stderr.write(f"Warning: failed to reset to remote {full_remote_ref}: {str(e)}\n")
        else:
            try:
                run_git(["pull"], cwd=wt_path)
            except GitError as e:
                sys.stderr.write(f"Warning: pull failed: {str(e)}\n")
        return wt_path
        
    # If path directory exists on disk but is NOT registered as a worktree for this repo, clean it up
    if os.path.exists(target_path):
        sys.stderr.write(f"Stale directory found at {target_path}. Cleaning...\n")
        shutil.rmtree(target_path, ignore_errors=True)
        # Remove registered but missing worktrees
        try:
            run_git(["worktree", "prune"], cwd=cwd_abs)
        except GitError:
            pass
            
    # Create worktree
    sys.stderr.write(f"Creating new worktree for {branch_name} at {target_path}...\n")
    
    # If remote_ref exists and differs from local branch, check if local branch exists
    if remote_ref:
        try:
            # Safer, non-scraping check for local branch existence
            run_git(["show-ref", "--verify", f"refs/heads/{branch_name}"], cwd=cwd_abs)
            local_exists = True
        except GitError:
            local_exists = False
            
        if not local_exists:
            # Create local branch tracking remote branch (use '--' separator to avoid option injection)
            run_git(["branch", "--track", "--", branch_name, remote_ref], cwd=cwd_abs)
            
    # Add the worktree safely using '--' to prevent option injection
    run_git(["worktree", "add", target_path, "--", branch_name], cwd=cwd_abs)
    
    # Ensure reset to match remote if remote_ref is given
    if remote_ref:
        remote_name, full_remote_ref = parse_remote_ref(remote_ref, remotes)
        try:
            # No `--` separator: `git reset` treats `--` as the commit/pathspec split,
            # which would silently turn this into a no-op path reset.
            run_git(["reset", full_remote_ref], cwd=target_path)
        except GitError as e:
            sys.stderr.write(f"Warning: failed to reset new worktree to remote {full_remote_ref}: {str(e)}\n")
            
    return target_path

def main():
    if not HAS_FCNTL:
        print(json.dumps({"error": "Platform support: fcntl is required for file locking. This configuration is only supported on macOS and Linux."}))
        sys.exit(1)

    cwd = os.getcwd()
    try:
        toplevel = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
        os.chdir(toplevel)
        cwd = toplevel
    except GitError:
        print(json.dumps({"error": "Current directory is not inside a Git repository."}))
        sys.exit(1)
        
    # Parse CLI arguments
    target_input = None
    reference_override = None
    prune_flag = False
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--prune":
            prune_flag = True
            i += 1
        elif arg == "--reference":
            if i + 1 < len(args):
                reference_override = args[i+1]
                i += 2
            else:
                print(json.dumps({"error": "--reference requires a branch name"}))
                sys.exit(1)
        elif arg.startswith("--reference="):
            reference_override = arg[len("--reference="):]
            i += 1
        elif arg.startswith("-"):
            print(json.dumps({"error": f"Unknown option: {arg}"}))
            sys.exit(1)
        else:
            # Positional argument
            target_input = arg
            i += 1

    # Handle explicit prune command
    if prune_flag:
        wt_root = os.path.expanduser("~/.gemini/tmp/worktrees")
        if os.path.exists(wt_root):
            sys.stderr.write(f"Cleaning worktree directory {wt_root}...\n")
            shutil.rmtree(wt_root, ignore_errors=True)
        # Prune git registration
        try:
            run_git(["worktree", "prune"], cwd=cwd)
        except GitError as e:
            sys.stderr.write(f"Warning: git worktree prune failed: {str(e)}\n")
        print(json.dumps({"success": True, "message": "Worktree cache pruned successfully."}))
        sys.exit(0)

    # Validate the reference override if specified using cat-file to support -- separator
    if reference_override is not None:
        try:
            obj_type = run_git(["cat-file", "-t", "--", reference_override], cwd=cwd)
        except GitError:
            print(json.dumps({"error": f"Reference branch '{reference_override}' not found."}))
            sys.exit(1)
        if obj_type not in ("commit", "tag"):
            print(json.dumps({"error": f"Reference '{reference_override}' resolves to a {obj_type}, not a commit or tag."}))
            sys.exit(1)

    # Use a lock file to prevent race conditions during concurrent runs
    wt_root = os.path.expanduser("~/.gemini/tmp/worktrees")
    os.makedirs(wt_root, exist_ok=True)
    lock_path = os.path.join(wt_root, "resolve_branches.lock")
    
    try:
        with FileLock(lock_path):
            if reference_override:
                ref_branch = reference_override
            else:
                ref_branch = resolve_integration_branch(cwd)
                
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
            # If the top branch's timestamp is very close to others, say within AMBIGUITY_WINDOW_SECS,
            # flag it as ambiguous if there are multiple branches.
            ambiguous = False
            candidates = branches[:5]  # top 5 recent branches
            
            if len(candidates) > 1:
                # Check if any candidate's timestamp is within the window of the most recent one
                for i in range(1, len(candidates)):
                    if candidates[0]["timestamp"] - candidates[i]["timestamp"] <= AMBIGUITY_WINDOW_SECS:
                        ambiguous = True
                        break
                        
            # If user passed a specific branch target, we resolve that one directly
            selected_branch = None
            if target_input:
                # Reject if the user-supplied feature branch equals the resolved reference branch.
                # origin/ is hardcoded to match resolve_integration_branch, which only derives
                # ref_branch from origin or local refs. Update both together.
                if target_input == ref_branch or target_input in (f"refs/heads/{ref_branch}", f"refs/remotes/origin/{ref_branch}"):
                    print(json.dumps({"error": f"Reference branch and feature branch are the same: {ref_branch}"}))
                    sys.exit(1)
                # Match against candidates
                for cand in branches:
                    if cand["branch_name"] == target_input or cand["full_name"] == target_input:
                        selected_branch = cand
                        break
                if not selected_branch:
                    print(json.dumps({"error": f"Branch '{target_input}' not found."}))
                    sys.exit(1)
            else:
                selected_branch = candidates[0]
                
            # Refuse to run if resolved reference_branch == feature_branch
            if ref_branch == selected_branch["branch_name"]:
                print(json.dumps({"error": f"Reference branch and feature branch are the same: {ref_branch}"}))
                sys.exit(1)
                
            # If ambiguous and no explicit branch requested, let agent know so it can ask user
            if ambiguous and not target_input:
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
                        
            # If remote_ref not found, explicitly look up refs/remotes/*/<branch_name> with git show-ref
            if not remote_ref:
                for remote in remotes:
                    try:
                        ref_to_verify = f"refs/remotes/{remote}/{selected_branch['branch_name']}"
                        run_git(["show-ref", "--verify", ref_to_verify], cwd=cwd)
                        remote_ref = f"{remote}/{selected_branch['branch_name']}"
                        break
                    except GitError:
                        pass
                        
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
