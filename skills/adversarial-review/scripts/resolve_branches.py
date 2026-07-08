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

# Git command timeout (in seconds) used across fetches and other git actions.
GIT_TIMEOUT = 30

class GitError(Exception):
    """Custom exception raised when a Git command fails or times out."""
    pass

class FileLock:
    def __init__(self, lock_path: str):
        self.lock_path: str = lock_path
        self.lock_file = None

    def __enter__(self) -> "FileLock":
        self.lock_file = open(self.lock_path, "w")
        
        start_time = time.time()
        try:
            timeout = int(os.environ.get("LOCK_TIMEOUT_SECS", "15"))
        except ValueError:
            timeout = 15
            
        acquired = False
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except (BlockingIOError, OSError):
            sys.stderr.write("Another instance is running. Waiting for lock...\n")
            
        while not acquired:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Timed out waiting for file lock after {timeout} seconds.")
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (BlockingIOError, OSError):
                time.sleep(0.5)
                
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
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
    try:
        branch = run_git(["symbolic-ref", "--short", "HEAD"], cwd=cwd)
        if branch:
            return branch
    except GitError:
        pass
    
    try:
        branch = run_git(["branch", "--show-current"], cwd=cwd)
        if branch:
            return branch
    except GitError:
        pass
        
    try:
        commit_hash = run_git(["rev-parse", "--short", "HEAD"], cwd=cwd)
        if commit_hash:
            return commit_hash
    except GitError:
        pass
        
    return "HEAD"

def resolve_integration_branch(cwd):
    remotes = get_remotes(cwd)
    if "origin" in remotes:
        remotes = ["origin"] + [r for r in remotes if r != "origin"]
        
    # 1. symref refs/remotes/<remote>/HEAD for each remote
    for remote in remotes:
        try:
            symref = run_git(["symbolic-ref", f"refs/remotes/{remote}/HEAD"], cwd=cwd)
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

    return get_current_branch(cwd)

def fetch_all(cwd):
    try:
        run_git(["fetch", "--all", "--prune"], cwd=cwd, timeout=GIT_TIMEOUT)
    except GitError as e:
        sys.stderr.write(f"Warning: git fetch failed: {str(e)}\n")

def get_remotes(cwd):
    try:
        out = run_git(["remote"], cwd=cwd)
        list_remotes = [line.strip() for line in out.splitlines() if line.strip()]
        return list_remotes if list_remotes else ["origin"]
    except GitError:
        return ["origin"]

def get_recent_branches(cwd, ref_branch):
    remotes = get_remotes(cwd)
    remotes.sort(key=len, reverse=True)
    
    fmt = "%(refname)|%(committerdate:unix)|%(objectname)|%(subject)"
    out = run_git(["for-each-ref", "--sort=-committerdate", f"--format={fmt}", "refs/heads/", "refs/remotes/"], cwd=cwd)
    
    branches = []
    seen_branches = set()
    
    exclude_prefixes = [ref_branch, "HEAD"]
    for remote in remotes:
        exclude_prefixes.extend([
            f"{remote}/{ref_branch}",
            f"remotes/{remote}/{ref_branch}",
            f"{remote}/HEAD",
            f"remotes/{remote}/HEAD"
        ])
    
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
            
        if refname.startswith("refs/heads/"):
            name = refname[len("refs/heads/"):]
        elif refname.startswith("refs/remotes/"):
            name = refname[len("refs/remotes/"):]
        else:
            name = refname
            
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
                if ref.startswith("refs/heads/"):
                    ref = ref[len("refs/heads/"):]
                current_wt["branch"] = ref
    if current_wt:
        worktrees.append(current_wt)
    return worktrees

def parse_remote_ref(remote_ref, remotes):
    full_remote_ref = remote_ref
    for prefix in ["refs/remotes/", "remotes/"]:
        if full_remote_ref.startswith(prefix):
            full_remote_ref = full_remote_ref[len(prefix):]
            break
            
    for remote in remotes:
        if full_remote_ref.startswith(f"{remote}/"):
            return remote, full_remote_ref
            
    return "origin", full_remote_ref

def is_managed_path(path, repo_hash, wt_root_abs):
    path = os.path.abspath(path)
    if not path.startswith(wt_root_abs + os.sep) and path != wt_root_abs:
        return False
    filename = os.path.basename(path)
    return filename.startswith(f"{repo_hash}_")

def setup_worktree(cwd, branch_name, remote_ref=None, commit_hash=None):
    cwd_abs = os.path.abspath(cwd)
    repo_hash = hashlib.sha256(cwd_abs.encode("utf-8")).hexdigest()[:8]
    
    clean_folder = branch_name.replace("/", "_").replace("\\", "_")
    clean_folder = "".join(c for c in clean_folder if c.isalnum() or c in ("-", "_", "."))
    
    branch_hash = hashlib.sha256(branch_name.encode("utf-8")).hexdigest()[:6]
    safe_folder = f"{clean_folder}_{branch_hash}"
    
    if not safe_folder or safe_folder in (".", ".."):
        raise ValueError(f"Unsafe branch name: {branch_name}")
        
    wt_root = os.path.expanduser("~/.gemini/tmp/worktrees")
    os.makedirs(wt_root, exist_ok=True)
    wt_root_abs = os.path.abspath(wt_root)
    
    target_path = os.path.abspath(os.path.join(wt_root_abs, f"{repo_hash}_{safe_folder}"))
    
    if not target_path.startswith(wt_root_abs + os.sep) and target_path != wt_root_abs:
        raise ValueError("Path traversal attempt detected in worktree setup.")
    
    wt_list = get_worktree_map(cwd_abs)
    
    existing_wt = None
    for wt in wt_list:
        if wt.get("path") == target_path:
            existing_wt = wt
            break
            
    remotes = get_remotes(cwd_abs)
    target_sha_or_ref = commit_hash if commit_hash else (remote_ref if remote_ref else branch_name)

    if existing_wt:
        if is_managed_path(target_path, repo_hash, wt_root_abs):
            sys.stderr.write(f"Worktree for {branch_name} exists at {target_path}. Checking status...\n")
            
            # Check if dirty
            try:
                status_out = run_git(["status", "--porcelain"], cwd=target_path)
                is_dirty = bool(status_out.strip())
            except GitError:
                is_dirty = True
                
            if is_dirty:
                sys.stderr.write(f"Managed worktree at {target_path} is dirty. Recreating...\n")
                try:
                    run_git(["worktree", "remove", "--force", target_path], cwd=cwd_abs)
                except GitError:
                    shutil.rmtree(target_path, ignore_errors=True)
                    try:
                        run_git(["worktree", "prune"], cwd=cwd_abs)
                    except GitError:
                        pass
                existing_wt = None
            else:
                # Update clean managed worktree
                try:
                    if remote_ref:
                        remote_name, full_remote_ref = parse_remote_ref(remote_ref, remotes)
                        try:
                            run_git(["fetch", remote_name], cwd=cwd_abs, timeout=GIT_TIMEOUT)
                        except GitError as e:
                            sys.stderr.write(f"Warning: git fetch failed: {str(e)}\n")
                    
                    run_git(["checkout", "--detach", target_sha_or_ref], cwd=target_path)
                    run_git(["reset", "--hard", target_sha_or_ref], cwd=target_path)
                except GitError as e:
                    sys.stderr.write(f"Warning: failed to update worktree to {target_sha_or_ref}: {str(e)}\n")
                return target_path

    if not existing_wt:
        if os.path.exists(target_path):
            sys.stderr.write(f"Stale directory found at {target_path}. Cleaning...\n")
            shutil.rmtree(target_path, ignore_errors=True)
            try:
                run_git(["worktree", "prune"], cwd=cwd_abs)
            except GitError:
                pass
                
        sys.stderr.write(f"Creating new detached worktree for {branch_name} at {target_path}...\n")
        
        if remote_ref:
            remote_name, full_remote_ref = parse_remote_ref(remote_ref, remotes)
            try:
                run_git(["fetch", remote_name], cwd=cwd_abs, timeout=GIT_TIMEOUT)
            except GitError as e:
                sys.stderr.write(f"Warning: git fetch failed: {str(e)}\n")
                
        run_git(["worktree", "add", "--detach", target_path, target_sha_or_ref], cwd=cwd_abs)
        
    return target_path

def main():
    if not HAS_FCNTL:
        print(json.dumps({"error": "Platform support: fcntl is required for file locking. This configuration is only supported on macOS and Linux."}))
        sys.exit(1)

    cwd = os.getcwd()
    try:
        toplevel = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
        cwd = toplevel
    except GitError:
        print(json.dumps({"error": "Current directory is not inside a Git repository."}))
        sys.exit(1)
        
    target_input = None
    reference_override = None
    prune_flag = False
    prune_all_flag = False
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--prune":
            prune_flag = True
            i += 1
        elif arg == "--prune-all":
            prune_flag = True
            prune_all_flag = True
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
            target_input = arg
            i += 1

    if prune_flag:
        cwd_abs = os.path.abspath(cwd)
        repo_hash = hashlib.sha256(cwd_abs.encode("utf-8")).hexdigest()[:8]
        wt_root = os.path.expanduser("~/.gemini/tmp/worktrees")
        
        if os.path.exists(wt_root):
            if prune_all_flag:
                sys.stderr.write(f"Cleaning all worktrees under {wt_root}...\n")
                shutil.rmtree(wt_root, ignore_errors=True)
            else:
                prefix = f"{repo_hash}_"
                sys.stderr.write(f"Cleaning worktrees matching prefix '{prefix}' under {wt_root}...\n")
                for item in os.listdir(wt_root):
                    if item.startswith(prefix):
                        item_path = os.path.join(wt_root, item)
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                        else:
                            try:
                                os.unlink(item_path)
                            except Exception:
                                pass
        try:
            run_git(["worktree", "prune"], cwd=cwd)
        except GitError as e:
            sys.stderr.write(f"Warning: git worktree prune failed: {str(e)}\n")
        
        msg = "All worktree caches pruned successfully." if prune_all_flag else f"Worktree cache for repo hash {repo_hash} pruned successfully."
        print(json.dumps({"success": True, "message": msg}))
        sys.exit(0)

    if reference_override is not None:
        try:
            obj_type = run_git(["cat-file", "-t", "--", reference_override], cwd=cwd)
        except GitError:
            print(json.dumps({"error": f"Reference branch '{reference_override}' not found."}))
            sys.exit(1)
        if obj_type not in ("commit", "tag"):
            print(json.dumps({"error": f"Reference '{reference_override}' resolves to a {obj_type}, not a commit or tag."}))
            sys.exit(1)

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
                
            # Determine ambiguity
            # A single clear candidate exists if:
            # 1. There is exactly one candidate branch.
            # 2. Or the current branch of the working copy is one of the candidates (and not the integration branch).
            # Otherwise, we mark it as ambiguous.
            ambiguous = False
            selected_branch = None
            current_local_branch = get_current_branch(cwd)
            
            if target_input:
                remotes = get_remotes(cwd)
                is_same = False
                if target_input == ref_branch or target_input == f"refs/heads/{ref_branch}":
                    is_same = True
                else:
                    for remote in remotes:
                        if target_input in (f"{remote}/{ref_branch}", f"refs/remotes/{remote}/{ref_branch}"):
                            is_same = True
                            break
                if is_same:
                    print(json.dumps({"error": f"Reference branch and feature branch are the same: {ref_branch}"}))
                    sys.exit(1)
                
                for cand in branches:
                    if cand["branch_name"] == target_input or cand["full_name"] == target_input:
                        selected_branch = cand
                        break
                if not selected_branch:
                    print(json.dumps({"error": f"Branch '{target_input}' not found."}))
                    sys.exit(1)
            else:
                if len(branches) == 1:
                    selected_branch = branches[0]
                else:
                    matching_current = [b for b in branches if b["branch_name"] == current_local_branch]
                    if len(matching_current) == 1:
                        selected_branch = matching_current[0]
                    else:
                        ambiguous = True
                        selected_branch = None
                        
            if ambiguous and not target_input:
                print(json.dumps({
                    "reference_branch": ref_branch,
                    "feature_branch": None,
                    "ambiguous": True,
                    "candidates": branches[:5]
                }, indent=2))
                sys.exit(0)
                
            if ref_branch == selected_branch["branch_name"]:
                print(json.dumps({"error": f"Reference branch and feature branch are the same: {ref_branch}"}))
                sys.exit(1)
                
            remote_ref = None
            remotes = get_remotes(cwd)
            for cand in branches:
                if cand["branch_name"] == selected_branch["branch_name"]:
                    is_remote = False
                    for remote in remotes:
                        if cand["full_name"].startswith(f"{remote}/") or cand["full_name"].startswith(f"remotes/{remote}/"):
                            is_remote = True
                            break
                    if is_remote:
                        remote_ref = cand["full_name"]
                        break
                        
            if not remote_ref:
                for remote in remotes:
                    try:
                        ref_to_verify = f"refs/remotes/{remote}/{selected_branch['branch_name']}"
                        run_git(["show-ref", "--verify", ref_to_verify], cwd=cwd)
                        remote_ref = f"{remote}/{selected_branch['branch_name']}"
                        break
                    except GitError:
                        pass
                        
            wt_path = setup_worktree(cwd, selected_branch["branch_name"], remote_ref, selected_branch["commit_hash"])
            
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
