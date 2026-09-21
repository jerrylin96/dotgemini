"""Load skills/git-signoff/attest.py and verify_signoff.py by path, the way the
shipped folder is used (no package install)."""

import importlib.util
import os

SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "skills", "git-signoff"))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SKILL_DIR, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


attest = _load("attest", "attest.py")
verify_signoff = _load("verify_signoff_for_attest_tests", "verify_signoff.py")
