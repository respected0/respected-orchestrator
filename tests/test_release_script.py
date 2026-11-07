import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "packaging" / "release.py"


class ReleaseScriptTest(unittest.TestCase):
    def test_every_written_version_agrees(self):
        spec = importlib.util.spec_from_file_location("release_script", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.check_versions(), "0.1.0-beta.3")


if __name__ == "__main__":
    unittest.main()
