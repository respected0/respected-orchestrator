"""B3-09.03: the installer script follows ADR-026. Static checks only (the script is compiled, never run, on a developer machine)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISS = (ROOT / "packaging" / "windows" / "orchestrator_setup.iss").read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def body(name):
    match = re.search(rf"^(?:procedure|function) {name}\b.*?^end;", ISS, re.S | re.M)
    assert match, name
    return match.group(0)


class UpdateWindowScriptTests(unittest.TestCase):
    def test_the_window_opens_and_work_drains_before_anything_is_stopped(self):
        prepare = body("PrepareToInstall")
        self.assertLess(prepare.index("DrainRunningWork()"), prepare.index("StopRunningProduct"))
        self.assertIn("if Result <> '' then Exit;", prepare)  # a refusal stops the update before any file or process is touched
        drain = body("DrainRunningWork")
        self.assertLess(drain.index("maintenance begin"), drain.index("maintenance drain"))
        self.assertNotIn("Stop-Process", drain)
        self.assertNotIn("DelTree", drain)

    def test_running_work_postpones_a_silent_update_and_asks_in_an_interactive_one(self):
        drain = body("DrainRunningWork")
        self.assertIn("Code <> 3", drain)  # exit 3 is the only "work is still running"
        silent = drain[drain.index("if WizardSilent then begin"):]
        self.assertIn("EndUpdateWindow", silent.split("end;")[0])
        self.assertIn("Hiçbir şey değiştirilmedi", silent)
        self.assertIn("MB_DEFBUTTON2", drain)  # the default answer is "No"
        self.assertIn("otomatik uygulanmazlar", drain)  # the person is told what a forced stop means

    def test_a_program_without_the_command_keeps_the_previous_behaviour(self):
        drain = body("DrainRunningWork")
        self.assertIn("is not available in the installed version", drain)
        self.assertIn("FileExists(ProgramExe())", drain)  # a first install has nothing running

    def test_the_window_is_closed_after_the_update_after_a_rollback_and_when_the_backup_fails(self):
        self.assertIn("EndUpdateWindow", body("CurStepChanged"))
        self.assertIn("EndUpdateWindow", body("RollBackUpdate"))
        self.assertIn("EndUpdateWindow", body("PrepareToInstall"))

    def test_the_existing_safety_net_is_still_in_place(self):
        self.assertIn("RollBackUpdate('güncellemeden sonra sağlıklı çalışmadı.')", body("CurStepChanged"))
        self.assertIn("BackUpForUpdate()", body("PrepareToInstall"))
        self.assertIn("UpdateBackup", ISS)

    def test_the_engine_knows_the_commands_the_script_calls(self):
        main = (ROOT / "src" / "respected_orchestrator" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn('"maintenance"', main)
        for action in ("begin", "end", "status", "drain"):
            self.assertIn(f'action == "{action}"', main)
        self.assertIn("0 if result[\"drained\"] else 3", main)  # the exit code the script tests


if __name__ == "__main__":
    unittest.main()
