import os
import sys
import unittest
import hashlib
import json
import shutil
import tempfile
from unittest.mock import patch

# Add scripts directory to path to import resolve_branches
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
import resolve_branches

class TestResolveBranches(unittest.TestCase):

    def setUp(self):
        # Keep every test away from the real ~/.gemini/tmp/worktrees
        self.wt_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.wt_root, True)
        env_patcher = patch.dict(os.environ, {"DOTGEMINI_WORKTREE_ROOT": self.wt_root})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        # "/Users/user/repo" hashes to "532a6759"
        self.repo_hash = hashlib.sha256("/Users/user/repo".encode("utf-8")).hexdigest()[:8]
        # "feature-branch" hashes to "8a76ef"
        self.branch_hash = hashlib.sha256("feature-branch".encode("utf-8")).hexdigest()[:6]

    def test_is_managed_path(self):
        # Valid managed path
        path1 = os.path.join(self.wt_root, f"{self.repo_hash}_my-branch_123456")
        self.assertTrue(resolve_branches.is_managed_path(path1, self.repo_hash, self.wt_root))

        # Path not in wt_root
        path2 = "/Users/user/projects/repo"
        self.assertFalse(resolve_branches.is_managed_path(path2, self.repo_hash, self.wt_root))

        # Path in wt_root but wrong repo prefix
        path3 = os.path.join(self.wt_root, "differenthash_my-branch_123456")
        self.assertFalse(resolve_branches.is_managed_path(path3, self.repo_hash, self.wt_root))

    @patch("resolve_branches.run_git")
    @patch("resolve_branches.get_worktree_map")
    def test_setup_worktree_creates_new_detached(self, mock_get_worktrees, mock_run_git):
        mock_get_worktrees.return_value = []
        mock_run_git.return_value = ""

        with patch("os.path.exists", return_value=False):
            resolve_branches.setup_worktree(
                cwd="/Users/user/repo",
                branch_name="feature-branch",
                remote_ref="origin/feature-branch",
                commit_hash="deadbeef"
            )

        # It should create a new detached worktree pointing to commit_hash
        # Verify git worktree add --detach is called
        added_worktree = False
        for call in mock_run_git.call_args_list:
            args = call[0][0]
            if "worktree" in args and "add" in args and "--detach" in args:
                added_worktree = True
                self.assertIn("deadbeef", args)
        
        self.assertTrue(added_worktree)
        # Ensure we never ran reset or stash in this flow
        for call in mock_run_git.call_args_list:
            args = call[0][0]
            self.assertNotIn("reset", args)
            self.assertNotIn("stash", args)

    @patch("resolve_branches.run_git")
    @patch("resolve_branches.get_worktree_map")
    def test_setup_worktree_reuses_clean_managed(self, mock_get_worktrees, mock_run_git):
        # Setup existing managed worktree at target path
        target_folder = f"feature-branch_{self.branch_hash}"
        target_path = os.path.join(self.wt_root, f"{self.repo_hash}_{target_folder}")

        mock_get_worktrees.return_value = [
            {"path": target_path, "branch": "feature-branch"}
        ]

        # First status call returns empty (not dirty)
        mock_run_git.side_effect = lambda args, cwd=None, timeout=None: "" if "status" in args else "mocked"

        wt_path = resolve_branches.setup_worktree(
            cwd="/Users/user/repo",
            branch_name="feature-branch",
            remote_ref="origin/feature-branch",
            commit_hash="deadbeef"
        )

        self.assertEqual(wt_path, target_path)

        # It should update using checkout --detach and reset --hard on the target path,
        # never on the primary repo (cwd).
        checkout_called = False
        reset_called = False
        
        for call in mock_run_git.call_args_list:
            args = call[0][0]
            kwargs = call[1] if len(call) > 1 else {}
            cwd_arg = kwargs.get("cwd")
            
            if "checkout" in args and "--detach" in args:
                checkout_called = True
                self.assertEqual(cwd_arg, target_path)
            if "reset" in args and "--hard" in args:
                reset_called = True
                self.assertEqual(cwd_arg, target_path)
                
        self.assertTrue(checkout_called)
        self.assertTrue(reset_called)

        # Assert no stash was pushed
        for call in mock_run_git.call_args_list:
            args = call[0][0]
            self.assertNotIn("stash", args)

    @patch("resolve_branches.run_git")
    @patch("resolve_branches.get_worktree_map")
    def test_setup_worktree_recreates_dirty_managed(self, mock_get_worktrees, mock_run_git):
        target_folder = f"feature-branch_{self.branch_hash}"
        target_path = os.path.join(self.wt_root, f"{self.repo_hash}_{target_folder}")

        mock_get_worktrees.return_value = [
            {"path": target_path, "branch": "feature-branch"}
        ]

        # Simulate dirty worktree status
        def mock_run(args, cwd=None, timeout=None):
            if "status" in args:
                return " M modified_file.py"
            return ""
        mock_run_git.side_effect = mock_run

        with patch("os.path.exists", return_value=True):
            resolve_branches.setup_worktree(
                cwd="/Users/user/repo",
                branch_name="feature-branch",
                remote_ref="origin/feature-branch",
                commit_hash="deadbeef"
            )

        # Since it was dirty, it should run git worktree remove --force
        remove_called = False
        for call in mock_run_git.call_args_list:
            args = call[0][0]
            if "worktree" in args and "remove" in args and "--force" in args:
                remove_called = True
                self.assertIn(target_path, args)
        
        self.assertTrue(remove_called)

    @patch("resolve_branches.run_git")
    @patch("resolve_branches.get_worktree_map")
    def test_setup_worktree_never_mutates_user_copy_if_checked_out_elsewhere(self, mock_get_worktrees, mock_run_git):
        # Simulate feature-branch checked out in the user's primary repo (/Users/user/repo)
        mock_get_worktrees.return_value = [
            {"path": "/Users/user/repo", "branch": "feature-branch"}
        ]
        mock_run_git.return_value = ""

        with patch("os.path.exists", return_value=False):
            wt_path = resolve_branches.setup_worktree(
                cwd="/Users/user/repo",
                branch_name="feature-branch",
                remote_ref="origin/feature-branch",
                commit_hash="deadbeef"
            )

        # Verify it still creates a new detached worktree in the managed cache path
        # and NEVER touches the user's primary copy (/Users/user/repo) for reset/stash/etc.
        target_folder = f"feature-branch_{self.branch_hash}"
        target_path = os.path.join(self.wt_root, f"{self.repo_hash}_{target_folder}")
        self.assertEqual(wt_path, target_path)

        added_worktree = False
        for call in mock_run_git.call_args_list:
            args = call[0][0]
            kwargs = call[1] if len(call) > 1 else {}
            cwd_arg = kwargs.get("cwd")
            
            if "worktree" in args and "add" in args:
                added_worktree = True
                self.assertIn(target_path, args)
                self.assertIn("--detach", args)
            
            # Ensure we did NOT reset or stash in /Users/user/repo
            if cwd_arg == "/Users/user/repo":
                self.assertNotIn("reset", args)
                self.assertNotIn("stash", args)

        self.assertTrue(added_worktree)

    @patch("resolve_branches.run_git")
    @patch("os.path.exists", return_value=True)
    @patch("os.scandir")
    @patch("resolve_branches.safe_rmtree")
    def test_prune_repo_prefix_only(self, mock_safe_rmtree, mock_scandir, mock_exists, mock_run_git):
        # Mock os.scandir to return DirEntry objects
        wt_root = self.wt_root
        class MockDirEntry:
            def __init__(self, name, is_dir_val=True, is_symlink_val=False):
                self.name = name
                self.path = os.path.join(wt_root, name)
                self.is_dir_val = is_dir_val
                self.is_symlink_val = is_symlink_val

            def is_dir(self, follow_symlinks=True):
                return self.is_dir_val

            def is_symlink(self):
                return self.is_symlink_val

        mock_scandir.return_value.__enter__.return_value = [
            MockDirEntry(f"{self.repo_hash}_branch1_123456"),
            MockDirEntry(f"{self.repo_hash}_branch2_789012"),
            MockDirEntry("differenthash_branch1_123456"),
            MockDirEntry("resolve_branches.lock", is_dir_val=False)
        ]

        with patch("sys.argv", ["resolve_branches.py", "--prune"]), patch("sys.exit", side_effect=SystemExit) as mock_exit:
            with patch("resolve_branches.os.path.abspath", return_value="/Users/user/repo"):
                with self.assertRaises(SystemExit):
                    resolve_branches.main()
                mock_exit.assert_called_once_with(0)
                
        # Verify safe_rmtree was called only on paths matching prefix and NOT on resolve_branches.lock
        removed_paths = [call[0][0] for call in mock_safe_rmtree.call_args_list]
        self.assertIn(os.path.join(self.wt_root, f"{self.repo_hash}_branch1_123456"), removed_paths)
        self.assertIn(os.path.join(self.wt_root, f"{self.repo_hash}_branch2_789012"), removed_paths)
        self.assertNotIn(os.path.join(self.wt_root, "differenthash_branch1_123456"), removed_paths)
        self.assertNotIn(os.path.join(self.wt_root, "resolve_branches.lock"), removed_paths)

    @patch("resolve_branches.run_git")
    def test_resolve_integration_branch_prefers_remote_default(self, mock_run_git):
        # Stale local main vs current origin/main.
        # Mock symbolic-ref to return refs/remotes/origin/main
        def mock_git(args, cwd=None, timeout=None):
            if "symbolic-ref" in args:
                return "refs/remotes/origin/main"
            if "remote" in args:
                return "origin"
            raise resolve_branches.GitError("Command failed")
            
        mock_run_git.side_effect = mock_git
        res = resolve_branches.resolve_integration_branch("/Users/user/repo")
        self.assertEqual(res, "origin/main")

    @patch("resolve_branches.run_git")
    def test_resolve_integration_branch_absent_local_main(self, mock_run_git):
        # Repos where local main is absent but remote default exists.
        # Mock symbolic-ref to fail, but show-ref to verify origin/main.
        def mock_git(args, cwd=None, timeout=None):
            if "remote" in args:
                return "origin"
            if "show-ref" in args and "refs/remotes/origin/main" in args:
                return "commit_hash"
            raise resolve_branches.GitError("Command failed")
            
        mock_run_git.side_effect = mock_git
        res = resolve_branches.resolve_integration_branch("/Users/user/repo")
        self.assertEqual(res, "origin/main")

    @patch("resolve_branches.run_git")
    def test_remote_only_reference(self, mock_run_git):
        def mock_git(args, cwd=None, timeout=None):
            if "remote" in args:
                return "origin"
            if "rev-parse" in args and "--show-toplevel" in args:
                return "/Users/user/repo"
            if "cat-file" in args:
                if "origin/release" in args or "release" in args:
                    return "commit"
            if "rev-parse" in args:
                if any("release" in str(a) for a in args):
                    return "commit_hash_123"
            raise resolve_branches.GitError("Command failed")
            
        mock_run_git.side_effect = mock_git
        
        import io
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture), patch("sys.exit", side_effect=SystemExit):
            with patch("sys.argv", ["resolve_branches.py", "--reference", "origin/release", "feat"]):
                with patch("resolve_branches.get_recent_branches") as mock_branches, \
                     patch("resolve_branches.setup_worktree", return_value="/tmp/wt"):
                    mock_branches.return_value = [{"branch_name": "feat", "full_name": "feat", "commit_hash": "feathash", "subject": "sub", "timestamp": 123}]
                    resolve_branches.main()
                    
        result = json.loads(stdout_capture.getvalue())
        self.assertEqual(result.get("reference_branch"), "origin/release")
        self.assertEqual(result.get("reference_ref"), "origin/release")
        self.assertEqual(result.get("reference_commit_hash"), "commit_hash_123")

    def _run_stale_local_main_integration(self, clean_after=False):
        import tempfile
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            origin_path = os.path.join(tmpdir, "origin")
            local_path = os.path.join(tmpdir, "local")
            os.makedirs(origin_path)
            
            def run_cmd(args, cwd):
                subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
            run_cmd(["git", "init", "-b", "main"], origin_path)
            run_cmd(["git", "config", "user.name", "Test User"], origin_path)
            run_cmd(["git", "config", "user.email", "test@example.com"], origin_path)
            with open(os.path.join(origin_path, "file.txt"), "w") as f:
                f.write("initial")
            run_cmd(["git", "add", "file.txt"], origin_path)
            run_cmd(["git", "commit", "-m", "initial commit"], origin_path)
            
            run_cmd(["git", "clone", origin_path, local_path], tmpdir)
            run_cmd(["git", "config", "user.name", "Test User"], local_path)
            run_cmd(["git", "config", "user.email", "test@example.com"], local_path)
            
            with open(os.path.join(origin_path, "file.txt"), "w") as f:
                f.write("updated remote")
            run_cmd(["git", "add", "file.txt"], origin_path)
            run_cmd(["git", "commit", "-m", "remote update"], origin_path)
            remote_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=origin_path, capture_output=True, text=True).stdout.strip()
            
            run_cmd(["git", "remote", "set-head", "origin", "main"], local_path)
            
            run_cmd(["git", "checkout", "-b", "feature-branch"], local_path)
            with open(os.path.join(local_path, "feature.txt"), "w") as f:
                f.write("feature changes")
            run_cmd(["git", "add", "feature.txt"], local_path)
            run_cmd(["git", "commit", "-m", "feature commit"], local_path)
            feature_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=local_path, capture_output=True, text=True).stdout.strip()
            
            old_cwd = os.getcwd()
            os.chdir(local_path)
            try:
                import io
                
                stdout_capture = io.StringIO()
                with patch("sys.stdout", stdout_capture), patch("sys.exit", side_effect=SystemExit):
                    with patch("sys.argv", ["resolve_branches.py", "feature-branch"]):
                        resolve_branches.main()
                        
                output_str = stdout_capture.getvalue()
                result = json.loads(output_str)
                
                self.assertEqual(result.get("reference_branch"), "origin/main")
                self.assertEqual(result.get("reference_ref"), "origin/main")
                self.assertEqual(result.get("reference_commit_hash"), remote_commit)
                self.assertEqual(result.get("commit_hash"), feature_commit)
                self.assertEqual(result.get("feature_branch"), "feature-branch")

                if clean_after:
                    stdout_capture_prune = io.StringIO()
                    with patch("sys.stdout", stdout_capture_prune), patch("sys.exit", side_effect=SystemExit):
                        with patch("sys.argv", ["resolve_branches.py", "--prune"]):
                            try:
                                resolve_branches.main()
                            except SystemExit:
                                pass
            finally:
                os.chdir(old_cwd)

    def test_integration_stale_local_main(self):
        import tempfile
        import shutil
        
        test_wt_root = tempfile.mkdtemp()
        try:
            with patch.dict(os.environ, {"DOTGEMINI_WORKTREE_ROOT": test_wt_root}):
                self._run_stale_local_main_integration()
        finally:
            shutil.rmtree(test_wt_root)

    def test_integration_qualified_target_names(self):
        # Remote-qualified (origin/foo) and refs-qualified (refs/heads/foo) target
        # names must resolve, and must review the exact ref that was requested even
        # when a same-named branch with a newer commit exists elsewhere.
        import tempfile
        import subprocess
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            origin_path = os.path.join(tmpdir, "origin")
            local_path = os.path.join(tmpdir, "local")
            os.makedirs(origin_path)

            def run_cmd(args, cwd):
                subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            def rev_parse(cwd):
                return subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True).stdout.strip()

            run_cmd(["git", "init", "-b", "main"], origin_path)
            run_cmd(["git", "config", "user.name", "Test User"], origin_path)
            run_cmd(["git", "config", "user.email", "test@example.com"], origin_path)
            with open(os.path.join(origin_path, "file.txt"), "w") as f:
                f.write("initial")
            run_cmd(["git", "add", "file.txt"], origin_path)
            run_cmd(["git", "commit", "-m", "initial commit"], origin_path)
            run_cmd(["git", "checkout", "-b", "foo"], origin_path)
            with open(os.path.join(origin_path, "file.txt"), "w") as f:
                f.write("remote foo")
            run_cmd(["git", "commit", "-am", "remote foo commit"], origin_path)
            remote_foo_commit = rev_parse(origin_path)
            run_cmd(["git", "checkout", "main"], origin_path)

            run_cmd(["git", "clone", origin_path, local_path], tmpdir)
            run_cmd(["git", "config", "user.name", "Test User"], local_path)
            run_cmd(["git", "config", "user.email", "test@example.com"], local_path)
            run_cmd(["git", "checkout", "-b", "foo", "origin/foo"], local_path)
            time.sleep(1)  # newer committer date so dedup keeps the local branch
            with open(os.path.join(local_path, "file.txt"), "w") as f:
                f.write("local foo")
            run_cmd(["git", "commit", "-am", "newer local foo commit"], local_path)
            local_foo_commit = rev_parse(local_path)
            run_cmd(["git", "checkout", "main"], local_path)

            def resolve(target):
                import io
                stdout_capture = io.StringIO()
                with patch("sys.stdout", stdout_capture), patch("sys.exit", side_effect=SystemExit):
                    with patch("sys.argv", ["resolve_branches.py", target]):
                        resolve_branches.main()
                return json.loads(stdout_capture.getvalue())

            old_cwd = os.getcwd()
            os.chdir(local_path)
            try:
                result = resolve("origin/foo")
                self.assertEqual(result.get("feature_branch"), "foo")
                self.assertEqual(result.get("feature_ref"), "origin/foo")
                self.assertEqual(result.get("commit_hash"), remote_foo_commit)

                result = resolve("refs/heads/foo")
                self.assertEqual(result.get("feature_branch"), "foo")
                self.assertEqual(result.get("commit_hash"), local_foo_commit)

                result = resolve("foo")
                self.assertEqual(result.get("feature_branch"), "foo")
                self.assertEqual(result.get("commit_hash"), local_foo_commit)
            finally:
                os.chdir(old_cwd)

    def test_integration_reference_short_normalization(self):
        import tempfile
        import subprocess
        import shutil
        from unittest.mock import patch
        
        test_wt_root = tempfile.mkdtemp()
        try:
            with patch.dict(os.environ, {"DOTGEMINI_WORKTREE_ROOT": test_wt_root}):
                with tempfile.TemporaryDirectory() as tmpdir:
                    origin_path = os.path.join(tmpdir, "origin")
                    local_path = os.path.join(tmpdir, "local")
                    os.makedirs(origin_path)
                    
                    def run_cmd(args, cwd):
                        subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                    run_cmd(["git", "init", "-b", "main"], origin_path)
                    run_cmd(["git", "config", "user.name", "Test User"], origin_path)
                    run_cmd(["git", "config", "user.email", "test@example.com"], origin_path)
                    with open(os.path.join(origin_path, "file.txt"), "w") as f:
                        f.write("initial")
                    run_cmd(["git", "add", "file.txt"], origin_path)
                    run_cmd(["git", "commit", "-m", "initial commit"], origin_path)
                    
                    run_cmd(["git", "checkout", "-b", "release"], origin_path)
                    with open(os.path.join(origin_path, "release.txt"), "w") as f:
                        f.write("release content")
                    run_cmd(["git", "add", "release.txt"], origin_path)
                    run_cmd(["git", "commit", "-m", "release commit"], origin_path)
                    remote_release_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=origin_path, capture_output=True, text=True).stdout.strip()
                    
                    run_cmd(["git", "checkout", "main"], origin_path)
                    
                    run_cmd(["git", "clone", origin_path, local_path], tmpdir)
                    run_cmd(["git", "config", "user.name", "Test User"], local_path)
                    run_cmd(["git", "config", "user.email", "test@example.com"], local_path)
                    
                    run_cmd(["git", "checkout", "-b", "feature-branch"], local_path)
                    with open(os.path.join(local_path, "feat.txt"), "w") as f:
                        f.write("feat content")
                    run_cmd(["git", "add", "feat.txt"], local_path)
                    run_cmd(["git", "commit", "-m", "feat commit"], local_path)
                    
                    old_cwd = os.getcwd()
                    os.chdir(local_path)
                    try:
                        import io
                        
                        stdout_capture = io.StringIO()
                        with patch("sys.stdout", stdout_capture), patch("sys.exit", side_effect=SystemExit):
                            with patch("sys.argv", ["resolve_branches.py", "--reference", "release", "feature-branch"]):
                                resolve_branches.main()
                                
                        result = json.loads(stdout_capture.getvalue())
                        self.assertEqual(result.get("reference_branch"), "origin/release")
                        self.assertEqual(result.get("reference_ref"), "origin/release")
                        self.assertEqual(result.get("reference_commit_hash"), remote_release_commit)
                    finally:
                        os.chdir(old_cwd)
        finally:
            shutil.rmtree(test_wt_root)

    def test_integration_stale_local_release_preference(self):
        import tempfile
        import subprocess
        import shutil
        from unittest.mock import patch
        
        test_wt_root = tempfile.mkdtemp()
        try:
            with patch.dict(os.environ, {"DOTGEMINI_WORKTREE_ROOT": test_wt_root}):
                with tempfile.TemporaryDirectory() as tmpdir:
                    origin_path = os.path.join(tmpdir, "origin")
                    local_path = os.path.join(tmpdir, "local")
                    os.makedirs(origin_path)
                    
                    def run_cmd(args, cwd):
                        subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                    run_cmd(["git", "init", "-b", "main"], origin_path)
                    run_cmd(["git", "config", "user.name", "Test User"], origin_path)
                    run_cmd(["git", "config", "user.email", "test@example.com"], origin_path)
                    with open(os.path.join(origin_path, "file.txt"), "w") as f:
                        f.write("initial")
                    run_cmd(["git", "add", "file.txt"], origin_path)
                    run_cmd(["git", "commit", "-m", "initial commit"], origin_path)
                    
                    run_cmd(["git", "checkout", "-b", "release"], origin_path)
                    run_cmd(["git", "checkout", "main"], origin_path)
                    
                    run_cmd(["git", "clone", origin_path, local_path], tmpdir)
                    run_cmd(["git", "config", "user.name", "Test User"], local_path)
                    run_cmd(["git", "config", "user.email", "test@example.com"], local_path)
                    
                    run_cmd(["git", "branch", "release", "origin/release"], local_path)
                    
                    run_cmd(["git", "checkout", "release"], origin_path)
                    with open(os.path.join(origin_path, "file2.txt"), "w") as f:
                        f.write("advanced content")
                    run_cmd(["git", "add", "file2.txt"], origin_path)
                    run_cmd(["git", "commit", "-m", "advanced commit"], origin_path)
                    advanced_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=origin_path, capture_output=True, text=True).stdout.strip()
                    run_cmd(["git", "checkout", "main"], origin_path)
                    
                    run_cmd(["git", "checkout", "-b", "feature-branch"], local_path)
                    with open(os.path.join(local_path, "feat.txt"), "w") as f:
                        f.write("feat content")
                    run_cmd(["git", "add", "feat.txt"], local_path)
                    run_cmd(["git", "commit", "-m", "feat commit"], local_path)
                    
                    old_cwd = os.getcwd()
                    os.chdir(local_path)
                    try:
                        import io
                        stdout_capture = io.StringIO()
                        with patch("sys.stdout", stdout_capture), patch("sys.exit", side_effect=SystemExit):
                            with patch("sys.argv", ["resolve_branches.py", "--reference", "release", "feature-branch"]):
                                resolve_branches.main()
                                
                        result = json.loads(stdout_capture.getvalue())
                        self.assertEqual(result.get("reference_branch"), "origin/release")
                        self.assertEqual(result.get("reference_ref"), "origin/release")
                        self.assertEqual(result.get("reference_commit_hash"), advanced_commit)
                    finally:
                        os.chdir(old_cwd)
        finally:
            shutil.rmtree(test_wt_root)

    def test_integration_reference_ambiguous(self):
        import tempfile
        import subprocess
        import shutil
        from unittest.mock import patch
        
        test_wt_root = tempfile.mkdtemp()
        try:
            with patch.dict(os.environ, {"DOTGEMINI_WORKTREE_ROOT": test_wt_root}):
                with tempfile.TemporaryDirectory() as tmpdir:
                    origin_path1 = os.path.join(tmpdir, "origin1")
                    origin_path2 = os.path.join(tmpdir, "origin2")
                    local_path = os.path.join(tmpdir, "local")
                    os.makedirs(origin_path1)
                    os.makedirs(origin_path2)
                    
                    def run_cmd(args, cwd):
                        subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                    run_cmd(["git", "init", "-b", "main"], origin_path1)
                    run_cmd(["git", "config", "user.name", "Test User"], origin_path1)
                    run_cmd(["git", "config", "user.email", "test@example.com"], origin_path1)
                    with open(os.path.join(origin_path1, "file.txt"), "w") as f:
                        f.write("initial")
                    run_cmd(["git", "add", "file.txt"], origin_path1)
                    run_cmd(["git", "commit", "-m", "initial commit"], origin_path1)
                    run_cmd(["git", "checkout", "-b", "release"], origin_path1)
                    run_cmd(["git", "checkout", "main"], origin_path1)
                    
                    run_cmd(["git", "init", "-b", "main"], origin_path2)
                    run_cmd(["git", "config", "user.name", "Test User"], origin_path2)
                    run_cmd(["git", "config", "user.email", "test@example.com"], origin_path2)
                    with open(os.path.join(origin_path2, "file.txt"), "w") as f:
                        f.write("initial")
                    run_cmd(["git", "add", "file.txt"], origin_path2)
                    run_cmd(["git", "commit", "-m", "initial commit"], origin_path2)
                    run_cmd(["git", "checkout", "-b", "release"], origin_path2)
                    run_cmd(["git", "checkout", "main"], origin_path2)
                    
                    run_cmd(["git", "clone", origin_path1, local_path], tmpdir)
                    run_cmd(["git", "config", "user.name", "Test User"], local_path)
                    run_cmd(["git", "config", "user.email", "test@example.com"], local_path)
                    
                    run_cmd(["git", "remote", "add", "upstream", origin_path2], local_path)
                    run_cmd(["git", "fetch", "upstream"], local_path)
                    
                    run_cmd(["git", "checkout", "-b", "feature-branch"], local_path)
                    
                    old_cwd = os.getcwd()
                    os.chdir(local_path)
                    try:
                        import io
                        
                        stdout_capture = io.StringIO()
                        with patch("sys.stdout", stdout_capture), patch("sys.exit", side_effect=SystemExit):
                            with patch("sys.argv", ["resolve_branches.py", "--reference", "release", "feature-branch"]):
                                with self.assertRaises(SystemExit):
                                    resolve_branches.main()
                                    
                        result = json.loads(stdout_capture.getvalue())
                        self.assertIn("ambiguous", result.get("error", ""))
                    finally:
                        os.chdir(old_cwd)
        finally:
            shutil.rmtree(test_wt_root)

    def test_integration_no_pollution(self):
        import tempfile
        import shutil
        from unittest.mock import patch
        
        test_wt_root = tempfile.mkdtemp()
        try:
            with patch.dict(os.environ, {"DOTGEMINI_WORKTREE_ROOT": test_wt_root}):
                self._run_stale_local_main_integration(clean_after=True)
            for entry in os.listdir(test_wt_root):
                full_path = os.path.join(test_wt_root, entry)
                self.assertFalse(os.path.isdir(full_path), f"Found worktree directory: {entry}")
        finally:
            shutil.rmtree(test_wt_root)

if __name__ == "__main__":
    unittest.main()
