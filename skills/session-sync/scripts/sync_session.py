#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import tarfile
import io
import argparse

class GitError(Exception):
    pass

def run_git(args, cwd, timeout=30):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=env
        )
    except subprocess.TimeoutExpired:
        raise GitError(f"Git command timed out: git {' '.join(args)}")
    if res.returncode != 0:
        raise GitError(res.stderr.strip() or f"Git command returned non-zero code {res.returncode}")
    return res.stdout.strip()

def check_workspace_clean(repo_root):
    out = run_git(["status", "--porcelain"], cwd=repo_root)
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    return len(lines) == 0, lines

def get_current_branch(repo_root):
    try:
        return run_git(["symbolic-ref", "--short", "HEAD"], cwd=repo_root)
    except GitError:
        # Detached HEAD
        return "HEAD"

def get_remote_url(repo_root):
    try:
        return run_git(["config", "--get", "remote.origin.url"], cwd=repo_root)
    except GitError:
        return ""

def push_session(repo_root, conversation_id, brain_dir):
    if not os.path.exists(brain_dir):
        print(json.dumps({"error": f"Brain directory does not exist: {brain_dir}"}))
        sys.exit(1)

    # 1. Resolve Git State
    commit_sha = run_git(["rev-parse", "HEAD"], cwd=repo_root)
    branch = get_current_branch(repo_root)
    remote = get_remote_url(repo_root)

    # 2. Get uncommitted changes (including untracked files via intent-to-add)
    untracked_out = run_git(["status", "--porcelain"], cwd=repo_root)
    untracked_files = [
        line[3:] for line in untracked_out.splitlines() if line.startswith("?? ")
    ]

    if untracked_files:
        run_git(["add", "-N"] + untracked_files, cwd=repo_root)

    try:
        patch_content = run_git(["diff", "HEAD"], cwd=repo_root)
    finally:
        if untracked_files:
            run_git(["reset", "--"] + untracked_files, cwd=repo_root)

    # run_git() strips trailing whitespace, but `git apply` rejects a patch
    # that lost its terminating newline ("corrupt patch at line N"). Restore it.
    if patch_content and not patch_content.endswith("\n"):
        patch_content += "\n"

    # 3. Create Tarball in Memory
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w:gz') as tar:
        # Add metadata.json
        metadata = {
            "conversation_id": conversation_id,
            "branch": branch,
            "commit": commit_sha,
            "remote": remote
        }
        meta_bytes = json.dumps(metadata, indent=2).encode('utf-8')
        tarinfo = tarfile.TarInfo(name="metadata.json")
        tarinfo.size = len(meta_bytes)
        tar.addfile(tarinfo, io.BytesIO(meta_bytes))

        # Add workspace.patch
        patch_bytes = patch_content.encode('utf-8')
        tarinfo = tarfile.TarInfo(name="workspace.patch")
        tarinfo.size = len(patch_bytes)
        tar.addfile(tarinfo, io.BytesIO(patch_bytes))

        # Add brain directory recursively
        for root, dirs, files in os.walk(brain_dir):
            for file in files:
                filepath = os.path.join(root, file)
                relpath = os.path.relpath(filepath, brain_dir)
                tarinfo = tar.gettarinfo(filepath, arcname=f"brain/{relpath}")
                with open(filepath, 'rb') as f:
                    tar.addfile(tarinfo, f)

    tar_bytes = tar_stream.getvalue()

    # 4. Write blob to Git Object DB
    proc = subprocess.Popen(
        ["git", "hash-object", "-w", "--stdin"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=repo_root
    )
    stdout, stderr = proc.communicate(input=tar_bytes)
    if proc.returncode != 0:
        print(json.dumps({"error": f"Failed to write blob: {stderr.decode().strip()}"}))
        sys.exit(1)
    blob_sha = stdout.decode().strip()

    # 5. Create Tree
    tree_input = f"100644 blob {blob_sha}\tsession.tar.gz\n"
    proc = subprocess.Popen(
        ["git", "mktree"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=repo_root
    )
    stdout, stderr = proc.communicate(input=tree_input.encode('utf-8'))
    if proc.returncode != 0:
        print(json.dumps({"error": f"Failed to write tree: {stderr.decode().strip()}"}))
        sys.exit(1)
    tree_sha = stdout.decode().strip()

    # 6. Create Commit
    commit_args = ["commit-tree", tree_sha, "-m", f"Sync session {conversation_id}"]
    
    # Link parent if reference exists
    parent_ref = f"refs/gemini-sessions/{conversation_id}"
    try:
        parent_sha = run_git(["rev-parse", parent_ref], cwd=repo_root)
        if parent_sha:
            commit_args += ["-p", parent_sha]
    except GitError:
        pass

    proc = subprocess.Popen(
        ["git"] + commit_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=repo_root
    )
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        print(json.dumps({"error": f"Failed to create commit: {stderr.decode().strip()}"}))
        sys.exit(1)
    commit_sha = stdout.decode().strip()

    # 7. Update Ref
    run_git(["update-ref", parent_ref, commit_sha], cwd=repo_root)

    # 8. Push Ref to Origin
    try:
        run_git(["push", "origin", parent_ref], cwd=repo_root)
    except GitError as e:
        print(json.dumps({"error": f"Failed to push ref to remote origin: {str(e)}"}))
        sys.exit(1)

    print(json.dumps({
        "success": True,
        "conversation_id": conversation_id,
        "ref": parent_ref,
        "commit": commit_sha
    }))

def pull_session(repo_root, conversation_id, brain_dir, on_dirty):
    ref_name = f"refs/gemini-sessions/{conversation_id}"

    # 1. Fetch from Origin
    try:
        run_git(["fetch", "origin", f"{ref_name}:{ref_name}"], cwd=repo_root)
    except GitError as e:
        print(json.dumps({"error": f"Failed to fetch session ref from remote: {str(e)}"}))
        sys.exit(1)

    # 2. Get Archive Blob
    try:
        proc = subprocess.Popen(
            ["git", "show", f"{ref_name}:session.tar.gz"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=repo_root
        )
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            print(json.dumps({"error": f"Failed to read archive from ref: {stderr.decode().strip()}"}))
            sys.exit(1)
        tar_bytes = stdout
    except Exception as e:
        print(json.dumps({"error": f"Error loading archive: {str(e)}"}))
        sys.exit(1)

    # 3. Read Tarball
    tar_stream = io.BytesIO(tar_bytes)
    try:
        with tarfile.open(fileobj=tar_stream, mode='r:gz') as tar:
            metadata = json.loads(tar.extractfile("metadata.json").read().decode('utf-8'))
            patch_content = tar.extractfile("workspace.patch").read().decode('utf-8')
    except Exception as e:
        print(json.dumps({"error": f"Malformed sync archive: {str(e)}"}))
        sys.exit(1)

    # 4. Check Workspace Cleanliness
    clean, dirty_files = check_workspace_clean(repo_root)
    stashed = False

    if not clean:
        if on_dirty == "abort":
            print(json.dumps({
                "status": "dirty",
                "message": "Workspace has uncommitted changes.",
                "files": dirty_files
            }))
            sys.exit(0)
        elif on_dirty == "stash":
            try:
                run_git(["stash", "-u"], cwd=repo_root)
                stashed = True
            except GitError as e:
                print(json.dumps({"error": f"Failed to stash changes: {str(e)}"}))
                sys.exit(1)
        elif on_dirty == "overwrite":
            try:
                run_git(["reset", "--hard"], cwd=repo_root)
                run_git(["clean", "-fd"], cwd=repo_root)
            except GitError as e:
                print(json.dumps({"error": f"Failed to discard changes: {str(e)}"}))
                sys.exit(1)

    # 5. Extract Session files to brain_dir
    try:
        os.makedirs(brain_dir, exist_ok=True)
        tar_stream.seek(0)
        with tarfile.open(fileobj=tar_stream, mode='r:gz') as tar:
            for member in tar.getmembers():
                if member.name.startswith("brain/"):
                    relpath = member.name[len("brain/"):]
                    target_path = os.path.abspath(os.path.join(brain_dir, relpath))
                    if not target_path.startswith(os.path.abspath(brain_dir) + os.sep):
                        print(json.dumps({"error": f"Path traversal detected: {member.name}"}))
                        sys.exit(1)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    f_in = tar.extractfile(member)
                    if f_in:
                        with open(target_path, 'wb') as f_out:
                            f_out.write(f_in.read())
    except Exception as e:
        # Recover
        if stashed:
            run_git(["stash", "pop"], cwd=repo_root)
        print(json.dumps({"error": f"Failed to extract session: {str(e)}"}))
        sys.exit(1)

    # 6. Align Workspace Branch & Patch
    target_branch = metadata.get("branch")
    parent_commit = metadata.get("commit")

    try:
        current_branch = get_current_branch(repo_root)
        
        # Best-effort fetch if parent_commit is missing locally
        if parent_commit:
            try:
                run_git(["cat-file", "-e", parent_commit], cwd=repo_root)
            except GitError:
                try:
                    run_git(["fetch", "origin", parent_commit], cwd=repo_root)
                except GitError:
                    if target_branch and target_branch != "HEAD":
                        try:
                            run_git(["fetch", "origin", f"{target_branch}:{target_branch}"], cwd=repo_root)
                        except GitError:
                            pass

        if target_branch and target_branch != "HEAD":
            if current_branch != target_branch:
                try:
                    run_git(["checkout", target_branch], cwd=repo_root)
                except GitError:
                    run_git(["checkout", "-b", target_branch, parent_commit], cwd=repo_root)
            if parent_commit:
                run_git(["reset", "--hard", parent_commit], cwd=repo_root)
        elif parent_commit:
            run_git(["checkout", parent_commit], cwd=repo_root)

        # Apply patch if it exists
        if patch_content.strip():
            proc = subprocess.Popen(
                ["git", "apply", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=repo_root
            )
            stdout, stderr = proc.communicate(input=patch_content.encode('utf-8'))
            if proc.returncode != 0:
                raise GitError(f"git apply failed: {stderr.decode().strip()}")

    except Exception as e:
        # Recover from failures
        if stashed:
            run_git(["stash", "pop"], cwd=repo_root)
        print(json.dumps({"error": f"Failed to restore workspace code state: {str(e)}"}))
        sys.exit(1)

    print(json.dumps({
        "success": True,
        "conversation_id": conversation_id,
        "branch": target_branch,
        "commit": parent_commit,
        "stashed": stashed
    }))

def list_sessions(repo_root):
    # Find local refs
    local_sessions = {}
    try:
        local_refs_out = run_git(["for-each-ref", "refs/gemini-sessions/*", "--format=%(refname) %(objectname) %(committerdate:iso-strict)"], cwd=repo_root)
        for line in local_refs_out.splitlines():
            if not line.strip():
                continue
            parts = line.split(None, 2)
            if len(parts) >= 2:
                ref = parts[0]
                sha = parts[1]
                date = parts[2] if len(parts) > 2 else "unknown"
                session_id = ref.replace("refs/gemini-sessions/", "")
                local_sessions[session_id] = {"sha": sha, "date": date, "local": True, "remote": False}
    except GitError:
        pass

    # Find remote refs
    remote_sessions = {}
    try:
        remote_refs_out = run_git(["ls-remote", "origin", "refs/gemini-sessions/*"], cwd=repo_root)
        for line in remote_refs_out.splitlines():
            if not line.strip():
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                sha, ref = parts
                session_id = ref.replace("refs/gemini-sessions/", "")
                remote_sessions[session_id] = {"sha": sha, "local": False, "remote": True}
    except GitError:
        pass

    # Merge lists
    all_sessions = {}
    for sid, info in local_sessions.items():
        all_sessions[sid] = info
    for sid, info in remote_sessions.items():
        if sid in all_sessions:
            all_sessions[sid]["remote"] = True
        else:
            all_sessions[sid] = {
                "sha": info["sha"],
                "date": "unknown (remote-only)",
                "local": False,
                "remote": True
            }

    print(json.dumps({
        "success": True,
        "sessions": all_sessions
    }, indent=2))

def clear_sessions(repo_root, conversation_id=None, clear_all=False):
    if not conversation_id and not clear_all:
        print(json.dumps({"error": "Must specify a conversation ID or use --all to clear all sessions."}))
        sys.exit(1)

    sessions_to_clear = []
    if clear_all:
        # Find all local sessions
        try:
            local_refs = run_git(["for-each-ref", "refs/gemini-sessions/*", "--format=%(refname)"], cwd=repo_root)
            for ref in local_refs.splitlines():
                if ref.strip():
                    sessions_to_clear.append(ref.strip().replace("refs/gemini-sessions/", ""))
        except GitError:
            pass
        
        # Find all remote sessions
        try:
            remote_refs = run_git(["ls-remote", "origin", "refs/gemini-sessions/*"], cwd=repo_root)
            for line in remote_refs.splitlines():
                if line.strip():
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        ref = parts[1]
                        sid = ref.replace("refs/gemini-sessions/", "")
                        if sid not in sessions_to_clear:
                            sessions_to_clear.append(sid)
        except GitError:
            pass
    else:
        sessions_to_clear = [conversation_id]

    if not sessions_to_clear:
        print(json.dumps({"success": True, "message": "No sessions found to clear.", "cleared": []}))
        return

    cleared = []
    errors = []
    for sid in sessions_to_clear:
        ref_name = f"refs/gemini-sessions/{sid}"
        remote_deleted = False
        local_deleted = False

        # 1. Delete Remote Ref
        try:
            run_git(["push", "origin", "--delete", ref_name], cwd=repo_root)
            remote_deleted = True
        except GitError as e:
            errors.append(f"Remote delete failed for {sid}: {str(e)}")

        # 2. Delete Local Ref
        try:
            run_git(["show-ref", "--verify", ref_name], cwd=repo_root)
            run_git(["update-ref", "-d", ref_name], cwd=repo_root)
            local_deleted = True
        except GitError:
            pass

        if remote_deleted or local_deleted:
            cleared.append({
                "conversation_id": sid,
                "local": local_deleted,
                "remote": remote_deleted
            })

    print(json.dumps({
        "success": len(errors) == 0 or len(cleared) > 0,
        "cleared": cleared,
        "errors": errors
    }, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Sync and restore conversation sessions via Git remote")
    subparsers = parser.add_subparsers(dest="action", required=True)

    push_parser = subparsers.add_parser("push")
    push_parser.add_argument("--conversation-id", default=os.environ.get("ANTIGRAVITY_CONVERSATION_ID"))
    push_parser.add_argument("--repo-root", default=os.getcwd())

    pull_parser = subparsers.add_parser("pull")
    pull_parser.add_argument("conversation_id")
    pull_parser.add_argument("--repo-root", default=os.getcwd())
    pull_parser.add_argument("--on-dirty", choices=["abort", "stash", "overwrite"], default="abort")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--repo-root", default=os.getcwd())

    clear_parser = subparsers.add_parser("clear")
    clear_parser.add_argument("conversation_id", nargs="?")
    clear_parser.add_argument("--all", action="store_true")
    clear_parser.add_argument("--repo-root", default=os.getcwd())

    args = parser.parse_args()

    # Find the top-level repo directory
    try:
        repo_root = run_git(["rev-parse", "--show-toplevel"], cwd=args.repo_root)
    except GitError:
        print(json.dumps({"error": "Specified path is not in a Git repository."}))
        sys.exit(1)

    if args.action == "push":
        if not args.conversation_id:
            print(json.dumps({"error": "No conversation ID provided and ANTIGRAVITY_CONVERSATION_ID is unset."}))
            sys.exit(1)
        brain_dir = os.path.expanduser(f"~/.gemini/antigravity-cli/brain/{args.conversation_id}")
        push_session(repo_root, args.conversation_id, brain_dir)
    elif args.action == "pull":
        brain_dir = os.path.expanduser(f"~/.gemini/antigravity-cli/brain/{args.conversation_id}")
        pull_session(repo_root, args.conversation_id, brain_dir, args.on_dirty)
    elif args.action == "list":
        list_sessions(repo_root)
    elif args.action == "clear":
        clear_sessions(repo_root, args.conversation_id, args.all)

if __name__ == "__main__":
    main()
