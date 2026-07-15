import unittest
from unittest.mock import patch
import sys
import os

# Insert scripts folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
import sync_session

class TestSyncSession(unittest.TestCase):

    @patch("sync_session.run_git")
    def test_check_workspace_clean(self, mock_run_git):
        # Clean workspace
        mock_run_git.return_value = ""
        clean, files = sync_session.check_workspace_clean("/dummy/repo")
        self.assertTrue(clean)
        self.assertEqual(files, [])

        # Dirty workspace
        mock_run_git.return_value = " M file.py\n?? untracked.txt"
        clean, files = sync_session.check_workspace_clean("/dummy/repo")
        self.assertFalse(clean)
        self.assertEqual(len(files), 2)

    @patch("sync_session.run_git")
    def test_get_current_branch(self, mock_run_git):
        mock_run_git.return_value = "main"
        branch = sync_session.get_current_branch("/dummy/repo")
        self.assertEqual(branch, "main")

        mock_run_git.side_effect = sync_session.GitError("detached HEAD")
        branch = sync_session.get_current_branch("/dummy/repo")
        self.assertEqual(branch, "HEAD")

if __name__ == "__main__":
    unittest.main()
