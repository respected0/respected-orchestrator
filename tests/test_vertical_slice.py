import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.engine.vertical_slice import (
    CodexCall,
    CodexOutcome,
    _usage,
    run_vertical_slice,
)


class VerticalSliceTest(unittest.TestCase):
    def test_usage_separates_reasoning_and_weights_cache(self) -> None:
        events = [{
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1100,
                "cached_input_tokens": 1000,
                "output_tokens": 200,
                "reasoning_output_tokens": 150,
            },
        }]
        usage = _usage(events)
        self.assertEqual(usage["raw_input_tokens"], 1100)
        self.assertEqual(usage["cached_input_tokens"], 1000)
        self.assertEqual(usage["output_tokens"], 200)
        self.assertEqual(usage["reasoning_tokens"], 150)
        self.assertEqual(usage["estimated_weighted_tokens"], 330)

    def test_workers_run_concurrently_without_master_polling(self) -> None:
        lock = threading.Lock()
        active = 0
        peak = 0

        def fake_call(call, **kwargs):
            nonlocal active, peak
            if call.role in {"fast", "complex"}:
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.15)
                with lock:
                    active -= 1
            outputs = {
                "master": '{"tasks":[{"id":"fast","objective":"fast task"},{"id":"complex","objective":"complex task"}]}',
                "fast": '{"status":"ok","summary":"fast"}',
                "complex": '{"status":"ok","summary":"complex"}',
                "master-review": '{"decision":"APPROVED"}',
                "final-review": 'APPROVED\nReady.',
            }
            return CodexOutcome(
                status="COMPLETE",
                output=outputs[call.role],
                usage={},
                events_path=call.run_root / "events.jsonl",
                stdout_path=call.run_root / "stdout.log",
                stderr_path=call.run_root / "stderr.log",
            )

        with mock.patch("respected_orchestrator.engine.vertical_slice.run_codex_call", side_effect=fake_call):
            with tempfile.TemporaryDirectory() as temporary:
                state = run_vertical_slice(
                    goal="demo",
                    job_root=Path(temporary) / "job",
                    repo_root=Path("."),
                    test_command=["python", "-c", "print('ok')"],
                )
        self.assertEqual(state["status"], "COMPLETE")
        self.assertEqual(state["master_polls_during_workers"], 0)
        self.assertEqual(peak, 2)

    def test_master_can_request_one_bounded_correction(self) -> None:
        calls = []

        def fake_call(call, **kwargs):
            calls.append(call.role)
            if call.role == "master":
                return CodexOutcome("COMPLETE", '{"tasks":[{"id":"fast","objective":"fast"},{"id":"complex","objective":"complex"}]}', {}, Path("a"), Path("b"), Path("c"))
            if call.role in {"fast", "complex"}:
                return CodexOutcome("COMPLETE", '{"status":"ok","summary":"worker"}', {}, Path("a"), Path("b"), Path("c"))
            if call.role == "master-review" and calls.count("master-review") == 1:
                return CodexOutcome("COMPLETE", '{"decision":"NEEDS_CHANGES","corrections":{"fast":"fix it"}}', {}, Path("a"), Path("b"), Path("c"))
            if call.role == "master-review":
                return CodexOutcome("COMPLETE", '{"decision":"APPROVED"}', {}, Path("a"), Path("b"), Path("c"))
            return CodexOutcome("COMPLETE", "APPROVED\nready", {}, Path("a"), Path("b"), Path("c"))

        with mock.patch("respected_orchestrator.engine.vertical_slice.run_codex_call", side_effect=fake_call):
            with tempfile.TemporaryDirectory() as temporary:
                state = run_vertical_slice(
                    goal="demo",
                    job_root=Path(temporary) / "job",
                    repo_root=Path("."),
                    test_command=["python", "-c", "print('ok')"],
                )
        self.assertEqual(state["status"], "COMPLETE")
        self.assertEqual(calls.count("fast"), 2)
        self.assertEqual(state["corrections"], {"fast": "fix it"})


if __name__ == "__main__":
    unittest.main()
