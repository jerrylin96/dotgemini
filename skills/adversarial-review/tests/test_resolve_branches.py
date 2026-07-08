import os
import sys
import unittest
import hashlib
from unittest.mock import patch

# Add scripts directory to path to import resolve_branches
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
import resolve_branches

class TestResolveBranches(unittest.TestCase):

    def setUp(self):
        self.wt_root = os.path.expanduser("~/.gemini/tmp/worktrees")
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
    @patch("shutil.rmtree")
    def test_setup_worktree_recreates_dirty_managed(self, mock_rmtree, mock_get_worktrees, mock_run_git):
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
        class MockDirEntry:
            def __init__(self, name, is_dir_val=True, is_symlink_val=False):
                self.name = name
                self.path = os.path.join(os.path.expanduser("~/.gemini/tmp/worktrees"), name)
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

if __name__ == "__main__":
    unittest.main()
