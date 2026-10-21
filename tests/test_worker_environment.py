"""Free regressions for cross-version PowerShell and bounded auth preflight."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator.engine.processes import execute
from tools import run_maf_coding_demo as demo


class WorkerEnvironmentTests(unittest.TestCase):
    def test_invalid_sandbox_marker_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            marker = home / ".sandbox" / "setup_marker.json"
            with self.assertRaisesRegex(RuntimeError, "no AI worker"):
                demo.preflight_sandbox(home)
            marker.parent.mkdir()
            for contents in ("", "not json", "[]", "{}"):
                marker.write_text(contents, encoding="utf8")
                with self.assertRaisesRegex(RuntimeError, "no AI worker"):
                    demo.preflight_sandbox(home)
                self.assertEqual(marker.read_text(encoding="utf8"), contents)
            marker.write_text('{"version":5}', encoding="utf8")
            self.assertIsNone(demo.preflight_sandbox(home))

    @unittest.skipUnless(sys.platform == "win32", "Windows demo preflight")
    def test_invalid_setup_stops_before_auth_git_or_worker(self):
        with mock.patch.object(demo, "get_cli_command", return_value=["fixture/codex"]), \
                mock.patch.object(demo, "preflight_sandbox", side_effect=RuntimeError("invalid setup")), \
                mock.patch.object(demo, "preflight_auth") as auth, \
                mock.patch.object(demo, "create_fixture") as fixture, \
                mock.patch.object(demo, "run_maf_coding_task") as worker:
            with self.assertRaisesRegex(RuntimeError, "invalid setup"):
                demo.main()
            auth.assert_not_called()
            fixture.assert_not_called()
            worker.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell environment regression")
    def test_child_does_not_inherit_powershell_module_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            for spelling in ("PSModulePath", "PSMODULEPATH"):
                env = {k: v for k, v in os.environ.items() if k.casefold() != "psmodulepath"}
                env[spelling] = "fixture-parent-PowerShell-modules"
                env["RESPECTED_ENV_FIXTURE"] = "preserved"
                command = [sys.executable, "-B", "-c",
                           "import os,json; print(json.dumps([os.getenv('PSModulePath'),os.getenv('RESPECTED_ENV_FIXTURE')]))"]
                result = execute(command, Path(temporary), 10, env=env)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout), [None, "preserved"])
                self.assertEqual(env[spelling], "fixture-parent-PowerShell-modules")

    def test_preflight_uses_existing_helper_without_editing_configs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source-config.toml"
            source.write_text('''model = "desktop-model"
model_provider = "openai"
[windows]
sandbox = "elevated"
[model_providers.evren1]
name = "Fixture"
base_url = "https://provider.invalid/v1"
wire_api = "responses"
[model_providers.evren1.auth]
command = "fixture-auth"
args = ["-Mode", "token"]
cwd = "fixture-cwd"
timeout_ms = 8000
[hooks]
enabled = true
[profiles.desktop]
model = "desktop-model"
[mcp_servers.fixture]
command = "must-not-start"
''', encoding="utf8")
            before = source.read_bytes()
            profile = root / "mimo.config.toml"
            profile.write_text('model_context_window=1000000\nmodel_reasoning_effort="high"\n'
                               '[projects.fixture]\ntrust_level="trusted"\n', encoding="utf8")
            profile_before = profile.read_bytes()
            with mock.patch.object(demo, "execute", return_value=mock.Mock(returncode=0, stdout="fixture-token")) as auth:
                self.assertIsNone(demo.preflight_auth(source))
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(profile.read_bytes(), profile_before)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["mimo.config.toml", "source-config.toml"])
            auth.assert_called_once_with(["fixture-auth", "-Mode", "token"], Path("fixture-cwd"), 8.0)

    def test_failed_auth_preflight_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.toml"
            source.write_text('[model_providers.evren1.auth]\ncommand="fixture"\nargs=[]\ncwd="fixture"\n', encoding="utf8")
            with mock.patch.object(demo, "execute", return_value=mock.Mock(returncode=2, stdout="")):
                with self.assertRaisesRegex(RuntimeError, "authentication"):
                    demo.preflight_auth(source)
            self.assertEqual([p.name for p in root.iterdir()], ["source.toml"])


if __name__ == "__main__":
    unittest.main()
