import json
import tempfile
import time
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import activity
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.journal import Journal, _encode
from respected_orchestrator.engine.local_api import LocalApi

TYPES = ("run.started", "review.requested", "run.failed", "approval.granted", "run.queued")


class ActivityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.journal = Journal(self.root / "events.log")

    def fill(self, n, types=TYPES):
        for i in range(n):
            self.journal.append(f"op-{i}", types[i % len(types)], f"run-{i % 7}", {"agent": "codex" if i % 2 else "claude", "i": i})

    def test_ten_thousand_events_page_completely_in_order_without_loss_or_repeat(self):
        self.fill(10_000)
        seen, cursor, pages = [], 0, 0
        started = time.monotonic()
        while True:
            page = activity.timeline(self.journal, cursor=cursor, limit=200)
            seen += [e["seq"] for e in page["events"]]
            cursor, pages = page["next_cursor"], pages + 1
            if not page["has_more"]:
                break
        self.assertEqual(seen, list(range(1, 10_001)))
        self.assertEqual(pages, 50)
        self.assertLess(time.monotonic() - started, 60)

    def test_filters_by_run_agent_stage_type_op_and_text(self):
        self.fill(70)
        by = lambda **kw: activity.timeline(self.journal, limit=200, **kw)["events"]
        self.assertEqual(len(by(run="run-3")), 10)
        self.assertTrue(all(e["run"] == "run-3" for e in by(run="run-3")))
        self.assertTrue(all(e["payload"]["agent"] == "codex" for e in by(agent="codex")))
        self.assertTrue(all(e["stage"] == "failed" for e in by(stages=["failed"])))
        self.assertEqual({e["type"] for e in by(types=["run.*"])}, {"run.started", "run.failed", "run.queued"})
        self.assertEqual([e["op"] for e in by(op="op-5")], ["op-5"])
        self.assertTrue(by(query="APPROVAL"))
        with self.assertRaises(ValueError):
            by(stages=["nope"])
        with self.assertRaises(ValueError):
            by(run=5)

    def test_unknown_types_and_hostile_payloads_are_shown_safely_not_dropped(self):
        self.journal.append("o1", "weird.thing", "run-1", {"text": "\x1b[31mred\x1b[0m\x07\x00bell", "big": "x" * 5000, "n": {"a": [1] * 200}})
        e = activity.timeline(self.journal)["events"][0]
        self.assertEqual((e["type"], e["stage"]), ("weird.thing", "unknown"))
        self.assertEqual(e["payload"]["text"], "redbell")
        self.assertEqual(len(e["payload"]["big"]), 300)
        self.assertEqual(len(e["payload"]["n"]["a"]), 40)

    def test_secrets_are_masked(self):
        self.journal.append("o1", "run.started", "run-1", {"api_key": "sk-abcdefghijklmnopqrstuvwxyz", "note": "Bearer abcdefghijklmnop12345"})
        self.assertNotIn("abcdefghijklmnop", json.dumps(activity.timeline(self.journal)))

    def test_out_of_order_timestamps_are_flagged_but_seq_order_wins(self):
        path = self.root / "ooo.log"
        with open(path, "ab") as f:
            for seq, ts in ((1, 1000.0), (2, 900.0), (3, 1001.0)):
                f.write(_encode(dict(v=1, seq=seq, ts=ts, op=f"o{seq}", run=None, type="run.started", p={})))
        page = activity.timeline(Journal(path))
        self.assertEqual([e["seq"] for e in page["events"]], [1, 2, 3])
        self.assertEqual([e["out_of_order"] for e in page["events"]], [False, True, False])

    def test_rotation_is_reported_as_missing_data_not_hidden(self):
        self.fill(5)
        self.journal.archive(self.root / "old.log")
        self.fill(3, types=("run.started",))
        page = activity.timeline(self.journal, cursor=2)
        self.assertTrue(page["missing_before"])
        self.assertEqual(page["events"][0]["type"], "journal.rotated")
        self.assertFalse(activity.timeline(self.journal, cursor=0)["missing_before"])

    def test_corrupt_tail_is_reported_and_trusted_prefix_is_returned(self):
        self.fill(5)
        with open(self.journal.path, "ab") as f:
            f.write(b"deadbeef {broken}\n")
        page = activity.timeline(Journal(self.journal.path))
        self.assertEqual(len(page["events"]), 5)
        self.assertTrue(page["corrupt"])

    def test_bad_cursor_and_limit_are_refused_and_limit_is_capped(self):
        self.fill(300)
        for bad in ({"cursor": -1}, {"cursor": "x"}, {"limit": 1.5}):
            with self.assertRaises(ValueError):
                activity.timeline(self.journal, **bad)
        self.assertEqual(len(activity.timeline(self.journal, limit=10_000)["events"]), 200)

    def test_empty_journal(self):
        page = activity.timeline(self.journal)
        self.assertEqual((page["events"], page["has_more"], page["first_seq"]), ([], False, None))

    def test_ipc_is_read_only_for_every_origin_and_validates(self):
        self.fill(3)
        ctx = EngineContext(self.root / "data")
        for n, origin in enumerate((Origin.RENDERER, Origin.MCP), 1):
            api = LocalApi(ctx, "t" * 32, origin=origin, journal=self.journal)
            ok = api.handle({"ipc": "1", "id": f"act-{n:05d}", "session": "t" * 32, "cmd": "activity.list", "payload": {"limit": 2}})
            self.assertTrue(ok["ok"] and len(ok["result"]["events"]) == 2, ok)
        bad = api.handle({"ipc": "1", "id": "act-00009", "session": "t" * 32, "cmd": "activity.list", "payload": {"cursor": -3}})
        self.assertEqual(bad["error"]["code"], "BAD_REQUEST")
        nojournal = LocalApi(ctx, "t" * 32).handle({"ipc": "1", "id": "act-00010", "session": "t" * 32, "cmd": "activity.list", "payload": {}})
        self.assertFalse(nojournal["ok"])


if __name__ == "__main__":
    unittest.main()
