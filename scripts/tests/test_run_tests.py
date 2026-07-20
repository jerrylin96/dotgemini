import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add scripts directory to path to import run_tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import run_tests

class TestRunTests(unittest.TestCase):
    @patch("shutil.which", return_value=None)
    @patch("os.path.exists", return_value=False)
    @patch("subprocess.run")
    @patch("sys.exit")
    def test_uv_missing_fallback(self, mock_exit, mock_run, mock_exists, mock_which):
        # Simulate uv missing: setup_success=False, fallback to host testing.
        with patch.dict(sys.modules, {"pytest": MagicMock()}):
            run_tests.main()
        
        mock_run.assert_called()
        cmd = mock_run.call_args[0][0]
        self.assertIn("-m", cmd)
        self.assertIn("pytest", cmd)

    @patch("shutil.which", return_value="/bin/uv")
    @patch("os.path.exists")
    @patch("subprocess.run")
    @patch("sys.exit", side_effect=SystemExit)
    def test_uv_present_setup_failure_no_fallback(self, mock_exit, mock_run, mock_exists, mock_which):
        def exists_side_effect(path):
            return os.path.basename(path) == "uv" or path.endswith("/uv")
        mock_exists.side_effect = exists_side_effect
        
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, ["setup_review_env.py"])
        
        with patch.dict(os.environ, {}):
            with self.assertRaises(SystemExit):
                run_tests.main()
            
        mock_exit.assert_called_once_with(1)

    @patch("shutil.which", return_value="/bin/uv")
    @patch("os.path.exists")
    @patch("subprocess.run")
    @patch("sys.exit")
    def test_uv_present_setup_failure_with_fallback(self, mock_exit, mock_run, mock_exists, mock_which):
        def exists_side_effect(path):
            return os.path.basename(path) == "uv" or path.endswith("/uv")
        mock_exists.side_effect = exists_side_effect
        
        import subprocess
        # First call fails (setup), second call succeeds (host pytest)
        mock_run.side_effect = [subprocess.CalledProcessError(1, ["setup_review_env.py"]), MagicMock()]
        
        with patch.dict(os.environ, {"ALLOW_HOST_TEST_FALLBACK": "1"}):
            with patch.dict(sys.modules, {"pytest": MagicMock()}):
                run_tests.main()
                
        self.assertEqual(mock_run.call_count, 2)
        second_call_cmd = mock_run.call_args_list[1][0][0]
        self.assertIn("pytest", second_call_cmd)

    @patch("shutil.which", return_value=None)
    @patch("os.path.exists")
    @patch("subprocess.run")
    @patch("sys.exit")
    def test_unittest_fallback(self, mock_exit, mock_run, mock_exists, mock_which):
        def exists_side_effect(path):
            filename = os.path.basename(path)
            if filename in ("uv", "pytest") or path.endswith("/uv") or path.endswith("/pytest"):
                return False
            return True
        mock_exists.side_effect = exists_side_effect

        # Simulate pytest missing on host by raising ImportError
        original_import = __import__
        def mock_import(name, *args, **kwargs):
            if name == "pytest":
                raise ImportError
            return original_import(name, *args, **kwargs)
            
        with patch("builtins.__import__", side_effect=mock_import):
            run_tests.main()
            
        called_dirs = []
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            if "-s" in cmd:
                idx = cmd.index("-s")
                called_dirs.append(cmd[idx + 1])
            
        self.assertIn("scripts/tests", called_dirs)
        self.assertIn("skills/adversarial-review/tests", called_dirs)
        self.assertIn("skills/data-autocleaning/tests", called_dirs)

if __name__ == "__main__":
    unittest.main()
