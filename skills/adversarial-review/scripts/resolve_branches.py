#!/usr/bin/env python3
import os
import re
import sys
import subprocess
import json
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

        try:
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
        except BaseException:
            self.lock_file.close()
            self.lock_file = None
            raise

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

def safe_rmtree(path: str):
    """
    Recursively remove a directory without following symlinks.
    """
    try:
        if os.path.islink(path):
            os.unlink(path)
            return
    except Exception:
        pass

    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_symlink():
                    try:
                        os.unlink(entry.path)
                    except Exception:
                        pass
                elif entry.is_dir(follow_symlinks=False):
                    safe_rmtree(entry.path)
                else:
                    try:
                        os.unlink(entry.path)
                    except Exception:
                        pass
        os.rmdir(path)
    except FileNotFoundError:
        pass
    except Exception as e:
        sys.stderr.write(f"Warning: failed to remove {path}: {e}\n")

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

def normalize_reference_ref(cwd: str, ref: str) -> str:
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]

    if ref.startswith("refs/remotes/"):
        ref = ref[len("refs/remotes/"):]

    try:
        remotes_out = run_git(["remote"], cwd=cwd)
        remotes = [r.strip() for r in remotes_out.splitlines() if r.strip()]
    except GitError:
        remotes = []

    has_remote_prefix = False
    for remote in remotes:
        if ref.startswith(f"{remote}/"):
            has_remote_prefix = True
            break

    if not has_remote_prefix:
        try:
            out = run_git(["for-each-ref", "--format=%(refname)", f"refs/remotes/*/{ref}"], cwd=cwd)
            matching_refs = [line.strip() for line in out.splitlines() if line.strip()]
            if len(matching_refs) == 1:
                matched = matching_refs[0]
                if matched.startswith("refs/remotes/"):
                    return matched[len("refs/remotes/"):]
                return matched
            elif len(matching_refs) > 1:
                options = []
                for r in matching_refs:
                    if r.startswith("refs/remotes/"):
                        options.append(r[len("refs/remotes/"):])
                    else:
                        options.append(r)
                print(json.dumps({"error": f"Reference '{ref}' is ambiguous. Found multiple remote branches: {', '.join(options)}. Please specify <remote>/{ref}."}))
                sys.exit(1)
        except GitError:
            pass

        try:
            run_git(["rev-parse", "--verify", f"refs/heads/{ref}"], cwd=cwd)
            return ref
        except GitError:
            pass
    else:
        try:
            run_git(["rev-parse", "--verify", f"refs/remotes/{ref}"], cwd=cwd)
            return ref
        except GitError:
            pass

    try:
        run_git(["rev-parse", "--verify", ref], cwd=cwd)
        return ref
    except GitError:
        pass

    return ref

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
                return symref[len("refs/remotes/"):] # e.g. "origin/main"
        except GitError:
            pass

    # 1b. If local main is absent but remote default/ref exists, check remote refs
    for remote in remotes:
        for possible in ["main", "master", "develop"]:
            try:
                run_git(["show-ref", "--verify", f"refs/remotes/{remote}/{possible}"], cwd=cwd)
                return f"{remote}/{possible}"
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
        return None
    except GitError as e:
        sys.stderr.write(f"Warning: git fetch failed: {str(e)}\n")
        return str(e)

def get_remotes(cwd):
    try:
        out = run_git(["remote"], cwd=cwd)
        list_remotes = [line.strip() for line in out.splitlines() if line.strip()]
        return list_remotes if list_remotes else ["origin"]
    except GitError:
        return ["origin"]

def get_remote_url(cwd, remote):
    try:
        return run_git(["remote", "get-url", remote], cwd=cwd)
    except GitError:
        return ""

def normalize_git_url(url):
    """Reduce a git remote URL to lowercase host/path form for comparison."""
    u = url.strip().lower()
    if u.startswith("git@"):
        u = u[len("git@"):].replace(":", "/", 1)
    else:
        for scheme in ("ssh://git@", "https://", "http://", "ssh://", "git://"):
            if u.startswith(scheme):
                u = u[len(scheme):]
                break
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[:-len(".git")]
    return u

PR_URL_PATTERNS = [
    # GitHub (/pull/42), Gitea/Forgejo (/pulls/42)
    re.compile(r"^(?P<base>https?://[^/\s]+/\S+?)/pulls?/(?P<num>\d+)(?:[/?#]\S*)?$", re.IGNORECASE),
    # GitLab (/-/merge_requests/42 or legacy /merge_requests/42)
    re.compile(r"^(?P<base>https?://[^/\s]+/\S+?)(?:/-)?/merge_requests/(?P<num>\d+)(?:[/?#]\S*)?$", re.IGNORECASE),
]

def parse_pr_target(target_input):
    """Return (pr_number, repo_url_or_None) if target_input names a PR/MR, else None.

    Recognized forms: '#42' and GitHub/GitLab/Gitea PR or MR web URLs. Bare numbers
    and branch names are never treated as PRs."""
    if not target_input:
        return None
    s = target_input.strip()
    m = re.fullmatch(r"#(\d+)", s)
    if m:
        return int(m.group(1)), None
    for pat in PR_URL_PATTERNS:
        m = pat.match(s)
        if m:
            return int(m.group("num")), m.group("base")
    return None

def resolve_pr_remote(cwd, repo_url):
    """Pick the remote whose URL matches repo_url; origin-preferred default when no URL given."""
    remotes = get_remotes(cwd)
    if "origin" in remotes:
        remotes = ["origin"] + [r for r in remotes if r != "origin"]
    if not repo_url:
        return remotes[0]
    want = normalize_git_url(repo_url)
    for remote in remotes:
        if normalize_git_url(get_remote_url(cwd, remote)) == want:
            return remote
    raise GitError(
        f"No git remote matches the PR URL repository '{repo_url}'. "
        f"Configured remotes: {', '.join(remotes)}. Add that repository as a remote, "
        f"or use --pr <N> if the PR lives on an already-configured remote."
    )

def pr_ref_candidates(remote_url, pr_number):
    """Server-side PR head refs to try, ordered by likelihood for the remote host."""
    github_style = f"refs/pull/{pr_number}/head"
    gitlab_style = f"refs/merge-requests/{pr_number}/head"
    if "gitlab" in normalize_git_url(remote_url):
        return [gitlab_style, github_style]
    return [github_style, gitlab_style]

def fetch_pr_head(cwd, remote, pr_number):
    """Fetch the PR head into refs/gemini-review/<remote>/pr/<N> (force-updated each
    run so re-reviews track new pushes). Returns (source_ref, local_ref).

    Unlike branch fetches, a failure here is fatal: a never-fetched PR ref has no
    stale local fallback to degrade to."""
    local_ref = f"refs/gemini-review/{remote}/pr/{pr_number}"
    remote_url = get_remote_url(cwd, remote)
    errors = []
    for src in pr_ref_candidates(remote_url, pr_number):
        try:
            run_git(["fetch", remote, f"+{src}:{local_ref}"], cwd=cwd, timeout=GIT_TIMEOUT)
            return src, local_ref
        except GitError as e:
            errors.append(str(e))
    raise GitError(
        f"Could not fetch PR/MR #{pr_number} from remote '{remote}'. "
        f"The PR may not exist, the network may be down, or the remote may not "
        f"expose PR refs (e.g. Bitbucket). Errors: {' | '.join(errors)}"
    )

def strip_ref_prefixes(name, remotes):
    """Reduce a possibly qualified ref (origin/foo, refs/heads/foo,
    refs/remotes/origin/foo) to its short branch name."""
    if name.startswith("refs/heads/"):
        return name[len("refs/heads/"):]
    if name.startswith("refs/remotes/"):
        rest = name[len("refs/remotes/"):]
        for remote in remotes:
            if rest.startswith(f"{remote}/"):
                return rest[len(f"{remote}/"):]
        parts = rest.split("/", 1)
        return parts[1] if len(parts) > 1 else rest
    for remote in remotes:
        if name.startswith(f"{remote}/"):
            return name[len(f"{remote}/"):]
    return name

def get_recent_branches(cwd, ref_branch):
    remotes = get_remotes(cwd)
    remotes.sort(key=len, reverse=True)
    
    fmt = "%(refname)|%(committerdate:unix)|%(objectname)|%(subject)"
    out = run_git(["for-each-ref", "--sort=-committerdate", f"--format={fmt}", "refs/heads/", "refs/remotes/"], cwd=cwd)
    
    branches = []
    seen_branches = set()
    
    short_ref_branch = ref_branch
    for remote in remotes:
        if ref_branch.startswith(f"{remote}/"):
            short_ref_branch = ref_branch[len(f"{remote}/"):]
            break
            
    exclude_prefixes = [ref_branch, short_ref_branch, "HEAD"]
    for remote in remotes:
        exclude_prefixes.extend([
            f"{remote}/{short_ref_branch}",
            f"remotes/{remote}/{short_ref_branch}",
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
        
    wt_root = os.environ.get("DOTGEMINI_WORKTREE_ROOT")
    if not wt_root:
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
                    safe_rmtree(target_path)
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
                    sys.stderr.write(f"Error: failed to update worktree to {target_sha_or_ref}: {str(e)}\n")
                    raise
                return target_path

    if not existing_wt:
        if os.path.exists(target_path):
            sys.stderr.write(f"Stale directory found at {target_path}. Cleaning...\n")
            safe_rmtree(target_path)
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
    pr_flag = None

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
        elif arg == "--pr":
            if i + 1 < len(args):
                pr_flag = args[i+1]
                i += 2
            else:
                print(json.dumps({"error": "--pr requires a PR/MR number"}))
                sys.exit(1)
        elif arg.startswith("--pr="):
            pr_flag = arg[len("--pr="):]
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

    pr_number = None
    pr_repo_url = None
    if pr_flag is not None:
        if target_input:
            print(json.dumps({"error": "--pr cannot be combined with a branch target."}))
            sys.exit(1)
        digits = pr_flag.lstrip("#")
        if not digits.isdigit():
            print(json.dumps({"error": f"--pr expects a PR/MR number, got '{pr_flag}'"}))
            sys.exit(1)
        pr_number = int(digits)
    elif target_input:
        parsed_pr = parse_pr_target(target_input)
        if parsed_pr:
            pr_number, pr_repo_url = parsed_pr
            target_input = None

    wt_root = os.environ.get("DOTGEMINI_WORKTREE_ROOT")
    if not wt_root:
        wt_root = os.path.expanduser("~/.gemini/tmp/worktrees")
    os.makedirs(wt_root, exist_ok=True)
    lock_path = os.path.join(wt_root, "resolve_branches.lock")

    if prune_flag:
        try:
            with FileLock(lock_path):
                cwd_abs = os.path.abspath(cwd)
                repo_hash = hashlib.sha256(cwd_abs.encode("utf-8")).hexdigest()[:8]
                
                if os.path.exists(wt_root):
                    if prune_all_flag:
                        sys.stderr.write(f"Cleaning all worktrees under {wt_root}...\n")
                        with os.scandir(wt_root) as it:
                            for entry in it:
                                if entry.name == "resolve_branches.lock":
                                    continue
                                if entry.is_symlink():
                                    try:
                                        os.unlink(entry.path)
                                    except Exception:
                                        pass
                                elif entry.is_dir(follow_symlinks=False):
                                    safe_rmtree(entry.path)
                                else:
                                    try:
                                        os.unlink(entry.path)
                                    except Exception:
                                        pass
                    else:
                        prefix = f"{repo_hash}_"
                        sys.stderr.write(f"Cleaning worktrees matching prefix '{prefix}' under {wt_root}...\n")
                        with os.scandir(wt_root) as it:
                            for entry in it:
                                if entry.name == "resolve_branches.lock":
                                    continue
                                if entry.name.startswith(prefix):
                                    if entry.is_symlink():
                                        try:
                                            os.unlink(entry.path)
                                        except Exception:
                                            pass
                                    elif entry.is_dir(follow_symlinks=False):
                                        safe_rmtree(entry.path)
                                    else:
                                        try:
                                            os.unlink(entry.path)
                                        except Exception:
                                            pass
                try:
                    run_git(["worktree", "prune"], cwd=cwd)
                except GitError as e:
                    sys.stderr.write(f"Warning: git worktree prune failed: {str(e)}\n")
                
                msg = "All worktree caches pruned successfully." if prune_all_flag else f"Worktree cache for repo hash {repo_hash} pruned successfully."
                print(json.dumps({"success": True, "message": msg}))
                sys.exit(0)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)

    try:
        with FileLock(lock_path):
            fetch_error = fetch_all(cwd)
            
            if reference_override is not None:
                reference_override = normalize_reference_ref(cwd, reference_override)
                try:
                    obj_type = run_git(["cat-file", "-t", "--", reference_override], cwd=cwd)
                except GitError:
                    print(json.dumps({"error": f"Reference branch '{reference_override}' not found."}))
                    sys.exit(1)
                if obj_type not in ("commit", "tag"):
                    print(json.dumps({"error": f"Reference '{reference_override}' resolves to a {obj_type}, not a commit or tag."}))
                    sys.exit(1)
                    
            if reference_override:
                ref_branch = reference_override
            else:
                curr = get_current_branch(cwd)
                ti_short = strip_ref_prefixes(target_input, get_remotes(cwd)) if target_input else target_input
                if curr and curr != "HEAD" and curr != ti_short:
                    ref_branch = curr
                else:
                    ref_branch = resolve_integration_branch(cwd)
                
            try:
                reference_commit_hash = run_git(["rev-parse", "--verify", f"{ref_branch}^{{commit}}"], cwd=cwd)
            except GitError:
                reference_commit_hash = None

            if pr_number is not None:
                try:
                    pr_remote = resolve_pr_remote(cwd, pr_repo_url)
                    pr_src_ref, pr_local_ref = fetch_pr_head(cwd, pr_remote, pr_number)
                except GitError as e:
                    print(json.dumps({"error": str(e)}))
                    sys.exit(1)
                commit_hash = run_git(["rev-parse", "--verify", f"{pr_local_ref}^{{commit}}"], cwd=cwd)
                subject = run_git(["log", "-1", "--format=%s", commit_hash], cwd=cwd)
                branch_name = f"pr-{pr_number}"
                wt_path = setup_worktree(cwd, branch_name, None, commit_hash)
                print(json.dumps({
                    "reference_branch": ref_branch,
                    "reference_ref": ref_branch,
                    "reference_commit_hash": reference_commit_hash,
                    "feature_branch": branch_name,
                    "feature_ref": f"{pr_remote}/{pr_src_ref[len('refs/'):]}",
                    "pr_number": pr_number,
                    "ambiguous": False,
                    "worktree_path": wt_path,
                    "commit_hash": commit_hash,
                    "subject": subject,
                    "fetch_error": fetch_error
                }, indent=2))
                sys.exit(0)

            branches = get_recent_branches(cwd, ref_branch)

            if not branches:
                print(json.dumps({
                    "reference_branch": ref_branch,
                    "reference_ref": ref_branch,
                    "reference_commit_hash": reference_commit_hash,
                    "feature_branch": None,
                    "ambiguous": False,
                    "candidates": [],
                    "message": "No other branches found to compare.",
                    "fetch_error": fetch_error
                }))
                sys.exit(0)
                
            selected_branch = None
            remotes = get_remotes(cwd)
            
            short_ref = ref_branch
            for remote in remotes:
                if ref_branch.startswith(f"{remote}/"):
                    short_ref = ref_branch[len(f"{remote}/"):]
                    break

            if not target_input:
                # Always prompt user to select target branch if not explicitly provided
                print(json.dumps({
                    "reference_branch": ref_branch,
                    "reference_ref": ref_branch,
                    "reference_commit_hash": reference_commit_hash,
                    "feature_branch": None,
                    "ambiguous": True,
                    "candidates": branches[:50],
                    "fetch_error": fetch_error
                }, indent=2))
                sys.exit(0)

            target_short = strip_ref_prefixes(target_input, remotes)

            if target_short == short_ref:
                print(json.dumps({"error": f"Reference branch and feature branch are the same: {ref_branch}"}))
                sys.exit(1)

            for cand in branches:
                if target_input in (cand["branch_name"], cand["full_name"]):
                    selected_branch = cand
                    break
            if not selected_branch:
                for cand in branches:
                    if target_short in (cand["branch_name"], cand["full_name"]):
                        selected_branch = cand
                        break
            if not selected_branch:
                print(json.dumps({"error": f"Branch '{target_input}' not found."}))
                sys.exit(1)

            # A qualified input (e.g. origin/foo) may have matched a candidate that was
            # deduplicated to a different ref of the same short name (e.g. local foo).
            # Honor the exact ref the user asked for.
            display_ref = target_input
            for prefix in ("refs/remotes/", "refs/heads/"):
                if display_ref.startswith(prefix):
                    display_ref = display_ref[len(prefix):]
                    break
            if target_input != target_short and display_ref != selected_branch["full_name"]:
                try:
                    exact_hash = run_git(["rev-parse", "--verify", f"{target_input}^{{commit}}"], cwd=cwd)
                    subject = run_git(["log", "-1", "--format=%s", exact_hash], cwd=cwd)
                    selected_branch = dict(selected_branch, full_name=display_ref,
                                           commit_hash=exact_hash, subject=subject)
                except GitError:
                    pass
                
            if short_ref == selected_branch["branch_name"]:
                print(json.dumps({"error": f"Reference branch and feature branch are the same: {ref_branch}"}))
                sys.exit(1)
                
            remote_ref = None
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
                "reference_ref": ref_branch,
                "reference_commit_hash": reference_commit_hash,
                "feature_branch": selected_branch["branch_name"],
                "feature_ref": selected_branch["full_name"],
                "ambiguous": False,
                "worktree_path": wt_path,
                "commit_hash": selected_branch["commit_hash"],
                "subject": selected_branch["subject"],
                "fetch_error": fetch_error
            }, indent=2))
            
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
