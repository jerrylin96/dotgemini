import os
import sys
import unittest
import tempfile
import shutil
import hashlib
import subprocess
from unittest.mock import patch

# Add scripts directory to path to import setup_review_env
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import setup_review_env
from scripts.file_lock import HAS_FCNTL  # noqa: E402

class TestSetupReviewEnv(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_fallback_parse_toml_multiline(self):
        toml_content = """
[project]
name = "test-project"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.20", # comment here
    "pandas#1.0.0", # comment with # inside quotes
]

[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-cov",
]
dev = [
    "black",
]
"""
        filepath = os.path.join(self.tmpdir, "pyproject.toml")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(toml_content)
            
        parsed = setup_review_env.fallback_parse_toml(filepath)
        
        # Verify correct project name and python version
        self.assertEqual(parsed.get("project", {}).get("name"), "test-project")
        self.assertEqual(parsed.get("project", {}).get("requires-python"), ">=3.11")
        
        # Verify dependencies parsed completely despite brackets and comments
        deps = parsed.get("project", {}).get("dependencies", [])
        self.assertIn("numpy>=1.20", deps)
        self.assertIn("pandas#1.0.0", deps)
        self.assertEqual(len(deps), 2)
        
        # Verify optional dependencies parsed completely
        opt_deps = parsed.get("project", {}).get("optional-dependencies", {})
        self.assertIn("test", opt_deps)
        self.assertIn("pytest>=7.0", opt_deps["test"])
        self.assertIn("pytest-cov", opt_deps["test"])
        self.assertIn("black", opt_deps.get("dev", []))

    def test_fingerprint_stability(self):
        # Fingerprint stability when nothing changes
        deps = ["pytest", "black", "numpy"]
        fp1 = setup_review_env.compute_fingerprint(self.tmpdir, deps)
        fp2 = setup_review_env.compute_fingerprint(self.tmpdir, deps)
        self.assertEqual(fp1, fp2)

        # Fingerprint changes when deps change
        deps_changed = ["pytest", "black", "numpy", "pandas"]
        fp3 = setup_review_env.compute_fingerprint(self.tmpdir, deps_changed)
        self.assertNotEqual(fp1, fp3)

        # Create a mock pyproject.toml
        pyproject_path = os.path.join(self.tmpdir, "pyproject.toml")
        with open(pyproject_path, "w") as f:
            f.write('name = "test"')
        fp4 = setup_review_env.compute_fingerprint(self.tmpdir, deps)
        self.assertNotEqual(fp1, fp4)

        # Modify pyproject.toml
        with open(pyproject_path, "w") as f:
            f.write('name = "test-modified"')
        fp5 = setup_review_env.compute_fingerprint(self.tmpdir, deps)
        self.assertNotEqual(fp4, fp5)

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/local/bin/uv")
    @patch("os.path.exists")
    @patch("sys.exit")
    def test_setup_review_env_targets_managed_env(self, mock_exit, mock_exists, mock_which, mock_run):
        # Track number of times we check for the python executable
        python_check_count = 0
        
        def exists_side_effect(path):
            nonlocal python_check_count
            if "uv" in path:
                return True
            if "pyproject.toml" in path:
                return True
            if "uv.lock" in path:
                return True
            if "bin/python" in path:
                python_check_count += 1
                # First check should return False to trigger venv creation.
                # Second check (during verification) should return True to pass.
                return python_check_count > 1
            if "bin/pytest" in path:
                return True
            if "bin/ruff" in path:
                return True
            return False
            
        mock_exists.side_effect = exists_side_effect
        
        # Mock load_pyproject to return simple project data
        with patch("setup_review_env.load_pyproject") as mock_load:
            mock_load.return_value = {
                "project": {
                    "name": "test-workspace",
                    "requires-python": ">=3.11",
                    "dependencies": ["requests"]
                }
            }
            
            # Run main using sys.argv patched
            with patch("sys.argv", ["setup_review_env.py", self.tmpdir]):
                setup_review_env.main()
                
        # Calculate expected env path
        path_hash = hashlib.sha256(self.tmpdir.encode('utf-8')).hexdigest()
        expected_env_path = os.path.join(os.path.expanduser("~/.gemini/tmp"), path_hash)
        
        # Verify that subprocess.run was called for venv, sync, and pip install
        # and that UV_PROJECT_ENVIRONMENT was set to expected_env_path in the environment
        venv_called = False
        sync_called = False
        pip_install_called = False
        
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            kwargs = call[1] if len(call) > 1 else {}
            env = kwargs.get("env", {})
            
            if "venv" in cmd:
                venv_called = True
                self.assertEqual(env.get("UV_PROJECT_ENVIRONMENT"), expected_env_path)
            elif "sync" in cmd:
                sync_called = True
                self.assertEqual(env.get("VIRTUAL_ENV"), expected_env_path)
                self.assertEqual(env.get("UV_PROJECT_ENVIRONMENT"), expected_env_path)
            elif "pip" in cmd and "install" in cmd:
                pip_install_called = True
                self.assertEqual(env.get("VIRTUAL_ENV"), expected_env_path)
                self.assertEqual(env.get("UV_PROJECT_ENVIRONMENT"), expected_env_path)
                
        self.assertTrue(venv_called)
        self.assertTrue(sync_called)
        self.assertTrue(pip_install_called)

    @patch("subprocess.run")
    @patch("os.path.exists", return_value=True)
    def test_check_venv_compatible(self, mock_exists, mock_run):
        mock_run.return_value.stdout = "3.11.0\n"
        self.assertTrue(setup_review_env.check_venv_compatible("/path/to/python", ">=3.10"))
        
        mock_run.return_value.stdout = "3.9.0\n"
        self.assertFalse(setup_review_env.check_venv_compatible("/path/to/python", ">=3.10"))
        
        mock_run.side_effect = subprocess.SubprocessError
        self.assertFalse(setup_review_env.check_venv_compatible("/path/to/python", ">=3.10"))

    def test_fallback_parse_toml_dependency_groups(self):
        toml_content = """
[project]
name = "test-project"

[project.optional-dependencies]
dev-cpu = [
    "torch-cpu",
]

[dependency-groups]
dev-tools = [
    "pytest",
    "black",
]
test = [
    "pytest-cov",
]
"""
        filepath = os.path.join(self.tmpdir, "pyproject.toml")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(toml_content)
            
        parsed = setup_review_env.fallback_parse_toml(filepath)
        opt_deps = parsed.get("project", {}).get("optional-dependencies", {})
        self.assertIn("dev-cpu", opt_deps)
        self.assertIn("torch-cpu", opt_deps["dev-cpu"])

        dep_groups = parsed.get("dependency-groups", {})
        self.assertIn("dev-tools", dep_groups)
        self.assertIn("pytest", dep_groups["dev-tools"])
        self.assertIn("black", dep_groups["dev-tools"])
        self.assertIn("test", dep_groups)
        self.assertIn("pytest-cov", dep_groups["test"])

    def test_check_venv_compatible_complex(self):
        # Mock subprocess.run
        with patch("subprocess.run") as mock_run, patch("os.path.exists", return_value=True):
            # Test ==3.10.*
            mock_run.return_value.stdout = "3.10.12\n"
            self.assertTrue(setup_review_env.check_venv_compatible("/bin/python", "==3.10.*"))
            
            mock_run.return_value.stdout = "3.11.0\n"
            self.assertFalse(setup_review_env.check_venv_compatible("/bin/python", "==3.10.*"))
            
            # Test ~=3.11
            mock_run.return_value.stdout = "3.11.5\n"
            self.assertTrue(setup_review_env.check_venv_compatible("/bin/python", "~=3.11"))
            
            mock_run.return_value.stdout = "4.0.0\n"
            self.assertFalse(setup_review_env.check_venv_compatible("/bin/python", "~=3.11"))
            
            mock_run.return_value.stdout = "3.10.9\n"
            self.assertFalse(setup_review_env.check_venv_compatible("/bin/python", "~=3.11"))

            # Test >=3.11,<3.12
            mock_run.return_value.stdout = "3.11.5\n"
            self.assertTrue(setup_review_env.check_venv_compatible("/bin/python", ">=3.11,<3.12"))
            
            mock_run.return_value.stdout = "3.12.0\n"
            self.assertFalse(setup_review_env.check_venv_compatible("/bin/python", ">=3.11,<3.12"))

            # Test !=3.11.0
            mock_run.return_value.stdout = "3.11.0\n"
            self.assertFalse(setup_review_env.check_venv_compatible("/bin/python", "!=3.11.0"))
            
            mock_run.return_value.stdout = "3.11.5\n"
            self.assertTrue(setup_review_env.check_venv_compatible("/bin/python", "!=3.11.0"))
            
            # Test complex case: >=3.11,!=3.11.0,<3.12
            mock_run.return_value.stdout = "3.11.0\n"
            self.assertFalse(setup_review_env.check_venv_compatible("/bin/python", ">=3.11,!=3.11.0,<3.12"))
            
            mock_run.return_value.stdout = "3.11.5\n"
            self.assertTrue(setup_review_env.check_venv_compatible("/bin/python", ">=3.11,!=3.11.0,<3.12"))
            
            mock_run.return_value.stdout = "3.12.0\n"
            self.assertFalse(setup_review_env.check_venv_compatible("/bin/python", ">=3.11,!=3.11.0,<3.12"))

            # Test fail closed on unknown syntax
            mock_run.return_value.stdout = "3.11.5\n"
            self.assertFalse(setup_review_env.check_venv_compatible("/bin/python", "bad_syntax_constraint"))

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_setup_review_env_locked_sync_failures(self, mock_exists, mock_run):
        mock_exists.side_effect = lambda path: True
        
        with patch("setup_review_env.load_pyproject") as mock_load:
            mock_load.return_value = {
                "project": {
                    "name": "test-locked-sync",
                    "requires-python": ">=3.11"
                }
            }
            
            # 1. Without ALLOW_UNLOCKED_SYNC=1, it should fail
            def run_side_effect(args, **kwargs):
                if "sync" in args and "--locked" in args:
                    raise subprocess.CalledProcessError(1, args)
                return unittest.mock.MagicMock()
            mock_run.side_effect = run_side_effect
            
            with patch("sys.argv", ["setup_review_env.py", self.tmpdir]), patch.dict(os.environ, {}):
                with self.assertRaises(subprocess.CalledProcessError):
                    setup_review_env.main()
                    
            # 2. With ALLOW_UNLOCKED_SYNC=1, it should retry without --locked
            mock_run.reset_mock()
            sync_unlocked_called = False
            
            def run_side_effect_2(args, **kwargs):
                nonlocal sync_unlocked_called
                if "sync" in args:
                    if "--locked" in args:
                        raise subprocess.CalledProcessError(1, args)
                    else:
                        sync_unlocked_called = True
                return unittest.mock.MagicMock()
                
            mock_run.side_effect = run_side_effect_2
            with patch("sys.argv", ["setup_review_env.py", self.tmpdir]), patch.dict(os.environ, {"ALLOW_UNLOCKED_SYNC": "1"}):
                setup_review_env.main()
            self.assertTrue(sync_unlocked_called)

    def test_file_lock_acquired(self):
        lock_path = os.path.join(self.tmpdir, "test.lock")
        
        # Test success under normal flock conditions
        if HAS_FCNTL:
            with setup_review_env.FileLock(lock_path):
                self.assertTrue(os.path.exists(lock_path))
                
            with patch("fcntl.flock", side_effect=OSError):
                with patch("time.time", side_effect=[0.0, 1000.0]):
                    with self.assertRaises(TimeoutError):
                        with setup_review_env.FileLock(lock_path):
                            pass

        # Test failure when fcntl is missing
        with patch("scripts.file_lock.HAS_FCNTL", False):
            with self.assertRaises(RuntimeError):
                with setup_review_env.FileLock(lock_path):
                    pass

if __name__ == "__main__":
    unittest.main()
