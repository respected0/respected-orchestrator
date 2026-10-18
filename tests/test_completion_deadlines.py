from pathlib import Path
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from respected_orchestrator.maf_workflow import review_timeout_default
from respected_orchestrator.processes import ProcessStopped, execute
from respected_orchestrator.runner import _workflow
from respected_orchestrator.vertical_slice import (
    CodexCall, _is_turn_completed, diagnose, run_codex_call, stream_verified_complete)

# Representative `codex exec --json` streams, replayed by a real local subprocess.
FAKE = r'''
import json, os, sys, time
def emit(**event):
    print(json.dumps(event), flush=True)
def message(text='{"decision": "APPROVED"}'):
    emit(type="item.completed", item={"id": "i1", "type": "agent_message", "text": text})
def done():
    emit(type="turn.completed", usage={"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 5})
scenario = os.environ["FAKE_SCENARIO"]
if scenario != "silent":
    emit(type="thread.started", thread_id="t")
    emit(type="turn.started")
if scenario == "complete_then_hang":
    message(); done(); time.sleep(60)
elif scenario == "complete_then_clean_exit":
    message(); done()
elif scenario == "complete_then_crash":
    message(); done(); sys.exit(3)
elif scenario == "completed_without_message":
    done(); time.sleep(60)
elif scenario == "failed_then_completed_hang":
    emit(type="turn.failed", error={"message": "stream disconnected before completion"}); message(); done(); time.sleep(60)
elif scenario == "reconnect_then_hang":
    emit(type="error", message="Reconnecting... 2/5 (stream disconnected)"); time.sleep(60)
elif scenario == "silent":
    time.sleep(60)
elif scenario == "active":
    while True:
        emit(type="item.updated", item={"type": "reasoning"}); time.sleep(0.2)
elif scenario == "stalled":
    emit(type="item.updated", item={"type": "reasoning"}); time.sleep(60)
elif scenario == "stderr_disconnect":
    print("stream disconnected", file=sys.stderr, flush=True); time.sleep(60)
'''


@unittest.skipUnless(os.name == "nt", "uses a .bat launcher")
class CodexStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        patcher = mock.patch("respected_orchestrator.vertical_slice.ACTIVE_WINDOW_SECONDS", 1)  # short runs
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.root / "fake_ai.py").write_text(FAKE, encoding="utf8")
        # Not named codex*, so the isolated-test guard stays active for real Codex binaries.
        self.launcher = self.root / "fake_ai.bat"
        self.launcher.write_text(f'@"{sys.executable}" "{self.root / "fake_ai.py"}" %*\r\n', encoding="utf8")

    def call(self, scenario, timeout, name="r"):
        with mock.patch.dict(os.environ, {"FAKE_SCENARIO": scenario}):
            started = time.monotonic()
            outcome = run_codex_call(CodexCall("reviewer", "p", None, "prompt", self.root / name), cwd=self.root,
                                     codex_path=str(self.launcher), timeout_seconds=timeout)
        return outcome, time.monotonic() - started

    def test_verified_completion_advances_without_waiting_for_deadline(self) -> None:
        outcome, elapsed = self.call("complete_then_hang", 40)
        self.assertEqual((outcome.status, outcome.cause), ("COMPLETE", "completed"))
        self.assertLess(elapsed, 20)
        self.assertEqual(self.call("complete_then_clean_exit", 40, "clean")[0].status, "COMPLETE")

    def test_failed_or_ambiguous_processes_never_become_success(self) -> None:
        for scenario in ("complete_then_crash", "completed_without_message", "failed_then_completed_hang"):
            with self.subTest(scenario):
                self.assertEqual(self.call(scenario, 40, scenario)[0].status, "FAILED")
        self.assertEqual(self.call("failed_then_completed_hang", 40, "x")[0].cause, "provider_disconnected")

    def test_timeout_classification_reports_uncertainty(self) -> None:
        for scenario, cause, confidence in (
                ("silent", "timeout_no_output", "unknown"),
                ("stalled", "timeout_stalled_after_output", "observed_output_timing"),
                ("reconnect_then_hang", "provider_disconnected", "structured"),
                ("stderr_disconnect", "provider_disconnected", "heuristic_stderr")):
            with self.subTest(scenario):
                outcome, elapsed = self.call(scenario, 3, scenario)
                self.assertEqual(outcome.status, "TIMEOUT")
                self.assertEqual((outcome.cause, outcome.diagnostics["confidence"]), (cause, confidence))
                self.assertLess(elapsed, 30)
        process = json.loads((self.root / "silent" / "process.json").read_text(encoding="utf8"))
        self.assertEqual(process["diagnostics"]["confidence"], "unknown")

    def test_activity_is_not_a_stall_and_still_hits_the_hard_deadline(self) -> None:
        outcome, elapsed = self.call("active", 3)
        self.assertEqual((outcome.status, outcome.cause), ("TIMEOUT", "timeout_active_at_deadline"))
        self.assertLess(elapsed, 30)


class ProcessCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    HANG = "import time;print('{\"type\":\"turn.completed\"}',flush=True);time.sleep(60)"

    def test_cancellation_outranks_a_late_completion(self) -> None:
        cancel = self.root / "cancel"
        threading.Timer(0.5, lambda: cancel.write_text("x")).start()
        with self.assertRaises(ProcessStopped) as raised:
            execute([sys.executable, "-c", self.HANG], self.root, 30, cancel_path=cancel,
                    complete_when=_is_turn_completed, verify_complete=stream_verified_complete)
        self.assertEqual(raised.exception.reason, "cancelled")

    def test_unverified_reaped_process_gets_nonzero_exit(self) -> None:
        result = execute([sys.executable, "-c", self.HANG], self.root, 30, complete_when=_is_turn_completed,
                         verify_complete=lambda stdout: False, exit_grace=0.2)
        self.assertNotEqual(result.returncode, 0)

    def test_verified_reaped_process_is_success_only_with_verification(self) -> None:
        result = execute([sys.executable, "-c", self.HANG], self.root, 30, complete_when=_is_turn_completed,
                         verify_complete=stream_verified_complete, exit_grace=0.2)
        self.assertEqual(result.returncode, 0)

    def test_silence_is_not_failure_until_the_deadline(self) -> None:
        result = execute([sys.executable, "-c", "import time;time.sleep(1.5);print('done')"], self.root, 30,
                         complete_when=_is_turn_completed)
        self.assertEqual(result.stdout.strip(), "done")
        with self.assertRaises(ProcessStopped) as raised:
            execute([sys.executable, "-c", "import time;print('working',flush=True);time.sleep(60)"], self.root, 1,
                    complete_when=_is_turn_completed)
        self.assertEqual(raised.exception.reason, "timed_out")
        self.assertTrue(raised.exception.had_output)

    def test_children_are_marked_so_they_cannot_approve(self) -> None:
        result = execute([sys.executable, "-c", "import os;print(os.environ.get('RESPECTED_ORCH_CHILD'))"],
                         self.root, 10)
        self.assertEqual(result.stdout.strip(), "1")


class PolicyTests(unittest.TestCase):
    def test_stream_verification_and_diagnosis_units(self) -> None:
        self.assertTrue(stream_verified_complete('{"type":"turn.completed"}\n'))
        self.assertFalse(stream_verified_complete('{"type":"turn.failed"}\n{"type":"turn.completed"}\n'))
        self.assertFalse(stream_verified_complete('{"type":"turn.started"}\n'))
        unknown = diagnose([], "", status="FAILED", had_output=False, last_output_age=None)
        self.assertEqual((unknown["cause"], unknown["confidence"]), ("failed", "unknown"))

    def test_review_deadline_is_provider_aware_and_still_validated(self) -> None:
        self.assertGreater(review_timeout_default("glm"), 300)
        self.assertGreater(review_timeout_default("GLM-5"), review_timeout_default("deepseek"))
        self.assertIsNone(_workflow({})["review_timeout_seconds"])
        self.assertIsNone(_workflow({})["timeout_seconds"])
        self.assertEqual(_workflow({"review_timeout_seconds": 600})["review_timeout_seconds"], 600)
        self.assertEqual(_workflow({"timeout_seconds": 7200})["timeout_seconds"], 7200)
        for key, bad in (("review_timeout_seconds", 0), ("review_timeout_seconds", 3601),
                         ("review_timeout_seconds", "5"), ("review_timeout_seconds", True),
                         ("timeout_seconds", 14401), ("timeout_seconds", 0)):
            with self.assertRaises(ValueError):
                _workflow({key: bad})


if __name__ == "__main__":
    unittest.main()
