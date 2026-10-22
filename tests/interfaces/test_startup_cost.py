"""Every Hub call starts the program once, so what an RPP manifest call imports is its cost."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = """
import json, sys
from respected_orchestrator.__main__ import main
main(["rpp"])
print(json.dumps(sorted(sys.modules)), file=sys.stderr)
"""


class StartupCostTest(unittest.TestCase):
    def loaded(self, op):
        with tempfile.TemporaryDirectory() as temp:
            env = {**os.environ, "RESPECTED_DATA_DIR": str(Path(temp) / "data"), "RESPECTED_APP_DIR": str(Path(temp) / "app"),
                   "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
            request = json.dumps({"rpp": "1", "op": op, "operation_id": None, "payload": {}})
            done = subprocess.run([sys.executable, "-c", PROBE], input=request, capture_output=True, text=True, env=env, cwd=temp, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(json.loads(done.stdout.splitlines()[0])["ok"], done.stdout)
        return set(json.loads(done.stderr.strip().splitlines()[-1]))

    def test_a_manifest_call_does_not_load_the_engine_the_roles_or_the_parser(self):
        loaded = self.loaded("manifest")
        for name in ("importlib.metadata", "argparse", "respected_orchestrator.engine.runner", "respected_orchestrator.workflows.roles",
                     "respected_orchestrator.interfaces.memory"):
            self.assertNotIn(name, loaded, f"manifest imports {name}")

    def test_a_health_call_does_not_read_the_package_metadata(self):
        self.assertNotIn("importlib.metadata", self.loaded("health"))

    def test_the_version_is_written_in_the_package_and_matches_pyproject(self):
        from packaging.version import Version
        import respected_orchestrator
        declared = re.search(r'(?m)^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8")).group(1)
        self.assertEqual(respected_orchestrator.__version__, str(Version(declared)))


if __name__ == "__main__":
    unittest.main()
