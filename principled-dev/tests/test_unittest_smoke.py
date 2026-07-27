import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from principled_dev.state import content_digest


class StandardLibrarySmokeTest(unittest.TestCase):
    def test_runtime_core_imports_without_third_party_dependencies(self):
        self.assertEqual(
            content_digest("principled-dev"),
            "aed2e22d234b68c0b52faf9e043992fa3942917c48b771d50f7d45bcd5e7fcd7",
        )


if __name__ == "__main__":
    unittest.main()
