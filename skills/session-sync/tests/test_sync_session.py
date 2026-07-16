import unittest
from unittest.mock import patch
import sys
import os
import io
import json
import shutil
import tempfile
import subprocess
from contextlib import redirect_stdout

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

    @patch("sync_session.run_git")
    def test_list_sessions(self, mock_run_git):
        def run_git_mock(args, cwd):
            if "for-each-ref" in args:
                return "refs/gemini-sessions/session-a sha-a 2026-07-16T10:00:00Z"
            elif "ls-remote" in args:
                return "sha-a\trefs/gemini-sessions/session-a\nsha-b\trefs/gemini-sessions/session-b"
            return ""
        mock_run_git.side_effect = run_git_mock

        buf = io.StringIO()
        with redirect_stdout(buf):
            sync_session.list_sessions("/dummy/repo")
        
        result = json.loads(buf.getvalue().strip())
        self.assertTrue(result["success"])
        sessions = result["sessions"]
        self.assertIn("session-a", sessions)
        self.assertIn("session-b", sessions)
        self.assertTrue(sessions["session-a"]["local"])
        self.assertTrue(sessions["session-a"]["remote"])
        self.assertFalse(sessions["session-b"]["local"])
        self.assertTrue(sessions["session-b"]["remote"])

    @patch("sync_session.run_git")
    def test_clear_sessions_specific(self, mock_run_git):
        mock_run_git.return_value = ""

        buf = io.StringIO()
        with redirect_stdout(buf):
            sync_session.clear_sessions("/dummy/repo", conversation_id="session-a")
        
        result = json.loads(buf.getvalue().strip())
        self.assertTrue(result["success"])
        self.assertEqual(len(result["cleared"]), 1)
        self.assertEqual(result["cleared"][0]["conversation_id"], "session-a")

    @patch("sync_session.run_git")
    def test_clear_sessions_all(self, mock_run_git):
        def run_git_mock(args, cwd):
            if "for-each-ref" in args:
                return "refs/gemini-sessions/session-a"
            elif "ls-remote" in args:
                return "sha-a\trefs/gemini-sessions/session-b"
            return ""
        mock_run_git.side_effect = run_git_mock

        buf = io.StringIO()
        with redirect_stdout(buf):
            sync_session.clear_sessions("/dummy/repo", clear_all=True)

        result = json.loads(buf.getvalue().strip())
        self.assertTrue(result["success"])
        cids = [c["conversation_id"] for c in result["cleared"]]
        self.assertIn("session-a", cids)
        self.assertIn("session-b", cids)


def _git(args, cwd):
    subprocess.run(
        ["git"] + args, cwd=cwd, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


class TestRoundTrip(unittest.TestCase):
    """End-to-end push -> pull across a shared bare remote."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Deterministic commit identity for git plumbing (commit-tree etc.)
        self._env = patch.dict(os.environ, {
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.co",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.co",
        })
        self._env.start()

    def tearDown(self):
        self._env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _capture(self, fn, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return json.loads(buf.getvalue().strip().splitlines()[-1])

    def test_push_pull_restores_uncommitted_and_untracked(self):
        remote = os.path.join(self.tmp, "remote.git")
        src = os.path.join(self.tmp, "src")
        dst = os.path.join(self.tmp, "dst")

        _git(["init", "--bare", "-b", "main", remote], cwd=self.tmp)
        _git(["init", "-b", "main", src], cwd=self.tmp)
        _git(["remote", "add", "origin", remote], cwd=src)
        with open(os.path.join(src, "file.txt"), "w") as f:
            f.write("v1\n")
        _git(["add", "file.txt"], cwd=src)
        _git(["commit", "-m", "initial"], cwd=src)
        _git(["push", "-u", "origin", "main"], cwd=src)

        # Uncommitted modification + brand-new untracked file.
        with open(os.path.join(src, "file.txt"), "a") as f:
            f.write("v2-uncommitted\n")
        with open(os.path.join(src, "untracked.txt"), "w") as f:
            f.write("new\n")

        cid = "roundtrip-1"
        brain_src = os.path.join(self.tmp, "brain_src")
        os.makedirs(brain_src)
        with open(os.path.join(brain_src, "transcript.json"), "w") as f:
            f.write('{"log": "hello"}')

        res = self._capture(sync_session.push_session, src, cid, brain_src)
        self.assertTrue(res.get("success"), res)

        # Push must not disturb the user's index (the staged-reset bug).
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=src,
            stdout=subprocess.PIPE, text=True,
        ).stdout
        self.assertIn(" M file.txt", status)
        self.assertIn("?? untracked.txt", status)

        # Fresh clone == "another machine".
        _git(["clone", remote, dst], cwd=self.tmp)
        brain_dst = os.path.join(self.tmp, "brain_dst")
        res = self._capture(sync_session.pull_session, dst, cid, brain_dst, "abort")
        self.assertTrue(res.get("success"), res)

        # Uncommitted change is re-applied (guards the stripped-newline bug).
        with open(os.path.join(dst, "file.txt")) as f:
            self.assertEqual(f.read(), "v1\nv2-uncommitted\n")
        # Untracked file is restored.
        self.assertTrue(os.path.exists(os.path.join(dst, "untracked.txt")))
        # Brain/session files are restored.
        with open(os.path.join(brain_dst, "transcript.json")) as f:
            self.assertEqual(f.read(), '{"log": "hello"}')


if __name__ == "__main__":
    unittest.main()
