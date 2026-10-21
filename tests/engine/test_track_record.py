"""Measured track record per (family, tool, profile) from signed run evidence (engine/track_record.py)."""
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import track_record
from respected_orchestrator.engine.evidence import save_signed


def run(ctx, name, request=None, status="completed", result=None, attempts=None):
    directory = ctx.data_root / "state" / name
    directory.mkdir(parents=True)
    save_signed(ctx, directory / "request.json", request or {"kind": "write", "worker": "codex", "worker_profile": "p"})
    save_signed(ctx, directory / "status.json", {"status": status})
    if result is not None:
        save_signed(ctx, directory / "result.json", result)
    if attempts is not None:
        save_signed(ctx, directory / "review-attempts.json", {"attempts": attempts})
    return directory


class TrackRecordTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ctx = EngineContext(Path(temp.name).resolve())

    def test_counts_write_and_review_attempts(self):
        run(self.ctx, "run-1", result={"usage": {"estimated_weighted_tokens": 10}, "duration_seconds": 4})
        run(self.ctx, "run-2", status="failed", result={"usage": {"estimated_weighted_tokens": 30}, "duration_seconds": 8},
            attempts=[{"tool": "claude", "profile": "x", "status": "COMPLETE", "duration_seconds": 2},
                      {"status": "TIMEOUT", "usage": {"estimated_weighted_tokens": True}}])
        table = track_record.stats(self.ctx.data_root)
        self.assertEqual(table[("write", "codex", "p")], {"runs": 2, "ok": 1, "avg_tokens": 20, "avg_seconds": 6})
        self.assertEqual(table[("read", "claude", "x")], {"runs": 1, "ok": 1, "avg_tokens": None, "avg_seconds": 2})
        self.assertEqual(table[("read", "codex", "")]["ok"], 0)  # booleans are not token counts

    def test_skips_running_custom_and_tampered_evidence(self):
        run(self.ctx, "run-1", status="running")
        run(self.ctx, "run-2", request={"kind": "write", "worker": "custom"})
        run(self.ctx, "run-3", request={"kind": "read", "worker": "codex"})
        bad = run(self.ctx, "run-4")
        (bad / "status.json").write_text('{"status": "completed"}')  # unsigned
        self.assertEqual(track_record.stats(self.ctx.data_root), {})

    def test_limit_and_lane_roots(self):
        for index in range(3):
            run(self.ctx, f"run-{index}")
        self.assertEqual(track_record.stats(self.ctx.data_root, limit=2)[("write", "codex", "p")]["runs"], 2)
        lane = EngineContext(self.ctx.data_root / "campaigns" / "camp-1" / "lanes" / "a")
        run(lane, "run-9")
        self.assertEqual(track_record.stats(self.ctx.data_root)[("write", "codex", "p")]["runs"], 4)


if __name__ == "__main__":
    unittest.main()
