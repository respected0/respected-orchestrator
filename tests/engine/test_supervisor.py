import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import supervisor as sup
from respected_orchestrator.engine.lanes import _pid_is_alive

ROOT = Path(__file__).resolve().parents[2]
HOLDER = """
import sys, time
from pathlib import Path
from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.supervisor import Supervisor, SupervisorBusy
try:
    s = Supervisor(EngineContext(Path(sys.argv[1]))).acquire()
except SupervisorBusy:
    print("busy", flush=True); sys.exit(3)
print("owner", flush=True)
time.sleep(float(sys.argv[2]))
"""
SLEEPER = "import time; time.sleep(120)"
WRITER = """
import sys
from pathlib import Path
from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.supervisor import Supervisor
s = Supervisor(EngineContext(Path(sys.argv[1]))).acquire()
print("owner", flush=True)
i = 0
while True:
    i += 1
    s.claim_run("run-%d" % (i % 7), 4000000 + i)
"""


def spawn(code, *args):
    return subprocess.Popen([sys.executable, "-c", code, *args], stdout=subprocess.PIPE, text=True,
                            env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name).resolve() / "data"
        self.ctx = EngineContext(self.data)
        self.procs = []
        self.addCleanup(self.reap)

    def reap(self):
        for p in self.procs:
            p.kill()
            p.wait()
            p.stdout.close()

    def start(self, code, *args):
        p = spawn(code, *args)
        self.procs.append(p)
        return p

    def test_second_supervisor_in_the_same_data_root_is_refused(self):
        with sup.Supervisor(self.ctx):
            with self.assertRaises(sup.SupervisorBusy):
                sup.Supervisor(self.ctx).acquire()
        sup.Supervisor(self.ctx).acquire().release()  # released cleanly

    def test_crashed_owner_frees_the_lock_without_any_pid_guessing(self):
        holder = self.start(HOLDER, str(self.data), "60")
        self.assertEqual(holder.stdout.readline().strip(), "owner")
        with self.assertRaises(sup.SupervisorBusy):
            sup.Supervisor(self.ctx).acquire()
        holder.kill()
        holder.wait()
        sup.Supervisor(self.ctx).acquire().release()

    def test_concurrent_starts_have_exactly_one_owner(self):
        procs = [self.start(HOLDER, str(self.data), "4") for _ in range(6)]
        answers = sorted(p.stdout.readline().strip() for p in procs)
        self.assertEqual(answers, ["busy"] * 5 + ["owner"])

    def test_elevated_session_is_refused(self):
        with mock.patch.object(sup, "_is_elevated", return_value=True):
            with self.assertRaises(PermissionError):
                sup.Supervisor(self.ctx).acquire()

    def test_claims_need_ownership_and_block_duplicate_starts(self):
        with self.assertRaises(sup.SupervisorBusy):
            sup.Supervisor(self.ctx).claim_run("run-a", 1)  # not acquired
        worker = self.start(SLEEPER)
        with sup.Supervisor(self.ctx) as s:
            s.claim_run("run-a", worker.pid)
            with self.assertRaises(sup.RunAlreadyClaimed):
                s.claim_run("run-a", 99999999)
            s.claim_run("run-a", worker.pid)  # same worker re-claiming is idempotent
            worker.kill()
            worker.wait()
            s.claim_run("run-a", 4242)  # dead worker: the claim is reclaimable
            self.assertEqual(s.claims()["run-a"], 4242)

    def test_supervisor_death_does_not_kill_the_run_and_the_run_stays_claimed(self):
        worker = self.start(SLEEPER)
        holder = self.start(HOLDER, str(self.data), "60")
        self.assertEqual(holder.stdout.readline().strip(), "owner")
        holder.kill()
        holder.wait()
        self.assertTrue(_pid_is_alive(worker.pid))
        with sup.Supervisor(self.ctx) as s:
            s.claim_run("run-b", worker.pid)
        with sup.Supervisor(self.ctx) as again:
            with self.assertRaises(sup.RunAlreadyClaimed):
                again.claim_run("run-b", 4243)
            again.release_run("run-b")
            self.assertNotIn("run-b", again.claims())

    def test_killing_the_supervisor_mid_write_never_leaves_a_torn_claims_file(self):
        for _ in range(5):
            writer = self.start(WRITER, str(self.data))
            self.assertEqual(writer.stdout.readline().strip(), "owner")
            time.sleep(0.4)
            writer.kill()
            writer.wait()
            with sup.Supervisor(self.ctx) as s:
                claims = s.claims()  # json.loads inside; a torn file would come back empty, a full one has all 7 slots
                self.assertEqual(sorted(claims), [f"run-{i}" for i in range(7)])


if __name__ == "__main__":
    unittest.main()
