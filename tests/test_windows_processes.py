"""No visible console windows from the engine's processes, and a clean life cycle for the processes it owns.

Root cause being guarded: supervisors run detached with no console, so every console program they start (git, python,
icacls...) opened its OWN visible window. All spawns now go through winproc / hidden_options."""
import inspect
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from respected_orchestrator import antigravity_orchestrator as agy, winproc
from respected_orchestrator.processes import ProcessStopped, execute

PY = sys.executable
SRC = Path(__file__).resolve().parents[1] / "src" / "respected_orchestrator"
WINDOWS = os.name == "nt"


def alive(pid):
    return agy._pid_is_alive(pid)


def wait_dead(pid, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not alive(pid):
            return True
        time.sleep(0.1)
    return False


class SpawnSitesTests(unittest.TestCase):
    def test_no_module_starts_a_process_without_the_hidden_window_helper(self):
        raw = re.compile(r"subprocess\.(run|Popen|call|check_call|check_output)\(")
        found = {path.name: len(raw.findall(path.read_text(encoding="utf8"))) for path in SRC.glob("*.py")}
        found = {name: count for name, count in found.items() if count}
        # winproc.run wraps subprocess.run; processes.execute and agy._spawn_detached each own their Popen call(s)
        self.assertEqual(found, {"winproc.py": 1, "processes.py": 1, "antigravity_orchestrator.py": 2})
        self.assertIn("winproc.hidden_options", inspect.getsource(agy._spawn_detached))
        self.assertNotIn("subprocess.DETACHED_PROCESS", inspect.getsource(agy._spawn_detached))  # a detached process has no console to share
        self.assertIn("winproc.hidden_options", (SRC / "processes.py").read_text(encoding="utf8"))

    @unittest.skipUnless(WINDOWS, "Windows console behaviour")
    def test_hidden_options_hide_the_window_and_keep_caller_flags(self):
        options = winproc.hidden_options(0x200)  # CREATE_NEW_PROCESS_GROUP
        self.assertTrue(options["creationflags"] & winproc.NO_WINDOW and options["creationflags"] & 0x200)
        self.assertEqual(options["startupinfo"].wShowWindow, 0)  # SW_HIDE
        with mock.patch("respected_orchestrator.winproc.subprocess.run") as run:
            winproc.run(["git", "--version"], creationflags=0x200, capture_output=True)
        flags = run.call_args.kwargs["creationflags"]
        self.assertTrue(flags & winproc.NO_WINDOW and flags & 0x200)
        self.assertIn("startupinfo", run.call_args.kwargs)

    def test_hidden_run_still_returns_output_errors_and_exit_codes(self):
        done = winproc.run([PY, "-c", "import sys; print('out'); sys.stderr.write('err'); sys.exit(3)"], capture_output=True, text=True)
        self.assertEqual((done.returncode, done.stdout.strip(), done.stderr), (3, "out", "err"))  # nothing is hidden but the window


PROBE = ("import ctypes, json, subprocess, sys\n"
         "def console():\n"
         "    handle = ctypes.windll.kernel32.GetConsoleWindow()\n"
         "    return [int(handle or 0), bool(handle and ctypes.windll.user32.IsWindowVisible(handle))]\n"
         "from respected_orchestrator import winproc\n"
         "probe = 'import ctypes; h = ctypes.windll.kernel32.GetConsoleWindow(); print(int(h or 0), bool(h and ctypes.windll.user32.IsWindowVisible(h)))'\n"
         "child = winproc.run([sys.executable, '-c', probe], capture_output=True, text=True).stdout.split()\n"
         "json.dump({'own': console(), 'child': child}, open(sys.argv[1], 'w'))\n")


@unittest.skipUnless(WINDOWS, "Windows console behaviour")
class DetachedSupervisorTests(unittest.TestCase):
    def test_a_detached_process_and_the_children_it_starts_have_no_visible_console(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "probe.py").write_text(PROBE, encoding="utf8")
            result = root / "result.json"
            env = dict(os.environ, PYTHONPATH=str(SRC.parent))
            pid = agy._spawn_detached([PY, str(root / "probe.py"), str(result)], root, root / "probe.log", env=env)
            deadline = time.monotonic() + 30
            while not result.exists() and time.monotonic() < deadline:
                time.sleep(0.2)
            self.assertTrue(result.exists(), (root / "probe.log").read_text(errors="replace"))
            self.assertTrue(wait_dead(pid))  # the supervisor stand-in ends and nothing of it lingers
            seen = json.loads(result.read_text())
        self.assertFalse(seen["own"][1], seen)  # a hidden console (or none), never a visible window
        self.assertEqual(seen["child"][-1], "False", seen)  # and its child did not open one either


class ProcessLifecycleTests(unittest.TestCase):
    """execute(): start, timeout, cancel and normal exit all leave no process of ours behind."""

    @staticmethod
    def tree_command(pid_file):
        code = ("import subprocess, sys, time; "
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
                f"open({str(pid_file)!r}, 'w').write(str(child.pid)); print('started', flush=True); time.sleep(120)")
        return [PY, "-c", code]

    def test_timeout_kills_the_whole_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            pid_file = Path(temporary) / "child.pid"
            with self.assertRaises(ProcessStopped) as stopped:
                execute(self.tree_command(pid_file), Path(temporary), 4)
            self.assertEqual(stopped.exception.reason, "timed_out")
            self.assertTrue(pid_file.exists())
            self.assertTrue(wait_dead(int(pid_file.read_text())), "grandchild survived the timeout")

    def test_cancel_kills_the_whole_tree_promptly(self):
        with tempfile.TemporaryDirectory() as temporary:
            pid_file, cancel = Path(temporary) / "child.pid", Path(temporary) / "cancel"
            threading.Timer(2.0, lambda: cancel.write_text("x")).start()
            started = time.monotonic()
            with self.assertRaises(ProcessStopped) as stopped:
                execute(self.tree_command(pid_file), Path(temporary), 60, cancel_path=cancel)
            self.assertEqual(stopped.exception.reason, "cancelled")
            self.assertLess(time.monotonic() - started, 20)
            self.assertTrue(wait_dead(int(pid_file.read_text())), "grandchild survived the cancel")

    @unittest.skipUnless(WINDOWS, "job objects")
    def test_an_orphan_left_by_a_finished_command_is_reaped(self):
        with tempfile.TemporaryDirectory() as temporary:
            pid_file = Path(temporary) / "orphan.pid"
            code = ("import subprocess, sys; "
                    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
                    f"open({str(pid_file)!r}, 'w').write(str(child.pid))")  # the parent exits at once, the child would live on
            done = execute([PY, "-c", code], Path(temporary), 30)
            self.assertEqual(done.returncode, 0)
            self.assertTrue(wait_dead(int(pid_file.read_text())), "orphan outlived the command")

    def test_a_missing_executable_is_reported_and_leaks_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(OSError):
                execute(["definitely-not-a-real-program-xyz"], Path(temporary), 5)


if __name__ == "__main__":
    unittest.main()
