import errno
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.engine.journal import Journal, mask


class JournalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "state" / "events.log"

    def test_ten_thousand_events_are_monotonic_and_replay_is_idempotent(self):
        j = Journal(self.path)
        for i in range(10000):
            j.append(f"op-{i}", "step", run_id="r1", payload={"i": i})
        seqs = [r["seq"] for r in j.replay()]
        self.assertEqual(seqs, list(range(1, 10001)))
        self.assertEqual(j.replay(), Journal(self.path).replay())
        self.assertEqual([r["seq"] for r in j.replay(after=9998)], [9999, 10000])
        self.assertEqual(len(j.replay(limit=5)), 5)

    def test_same_operation_and_type_is_stored_once(self):
        j = Journal(self.path)
        self.assertIsNotNone(j.append("op-1", "started"))
        self.assertIsNone(j.append("op-1", "started"))
        self.assertIsNotNone(j.append("op-1", "finished"))
        self.assertIsNone(Journal(self.path).append("op-1", "started"))  # survives restart
        self.assertEqual(j.last_seq, 2)

    def test_torn_tail_is_cut_and_the_journal_keeps_working(self):
        j = Journal(self.path)
        j.append("a", "x")
        j.append("b", "x")
        with open(self.path, "ab") as f:
            f.write(b"deadbeef {\"v\":1,\"seq\":3,")  # crash mid-write, no newline
        again = Journal(self.path)
        self.assertFalse(again.corrupt)
        self.assertEqual(again.last_seq, 2)
        self.assertEqual(again.append("c", "x")["seq"], 3)
        self.assertEqual(len(Journal(self.path).replay()), 3)

    def test_corruption_in_the_middle_returns_only_the_trusted_prefix_and_blocks_writes(self):
        j = Journal(self.path)
        for n in "abcd":
            j.append(n, "x")
        raw = bytearray(self.path.read_bytes())
        first_nl = raw.index(b"\n")
        raw[first_nl + 12] ^= 0xFF  # flip a byte inside record 2
        self.path.write_bytes(bytes(raw))
        before = self.path.read_bytes()
        bad = Journal(self.path)
        self.assertTrue(bad.corrupt)
        self.assertEqual([r["seq"] for r in bad.replay()], [1])
        with self.assertRaises(RuntimeError):
            bad.append("e", "x")
        self.assertEqual(self.path.read_bytes(), before)  # evidence left untouched

    def test_disk_full_raises_and_does_not_advance_or_poison_the_journal(self):
        j = Journal(self.path)
        j.append("a", "x")
        real_open = open

        def full(path, mode="r", *a, **k):
            if "a" in mode and str(path) == str(self.path):
                raise OSError(errno.ENOSPC, "No space left on device")
            return real_open(path, mode, *a, **k)
        with mock.patch("builtins.open", full):
            with self.assertRaises(OSError):
                j.append("b", "x")
        self.assertEqual(j.last_seq, 1)
        self.assertEqual(j.append("b", "x")["seq"], 2)  # the failed op was not remembered as stored

    def test_secrets_are_masked_before_they_reach_disk(self):
        j = Journal(self.path)
        j.append("s", "x", payload={"api_key": "sk-abcdefghijklmnop", "note": "token ghp_abcdefghijklmnopqrstuvwx used", "nested": [{"Authorization": "Bearer abcdefghijklmnop"}], "ok": 1})
        text = self.path.read_text()
        for leak in ("sk-abcdef", "ghp_abcdef", "Bearer abc", "abcdefghijklmnop"):
            self.assertNotIn(leak, text)
        self.assertIn('"ok":1', text)
        self.assertEqual(mask("plain"), "plain")

    def test_rotation_keeps_seq_monotonic_across_files(self):
        j = Journal(self.path)
        for n in "abc":
            j.append(n, "x")
        j.archive(self.path.with_suffix(".1"))
        self.assertEqual(j.append("d", "x")["seq"], 5)  # 4 is the rotation marker
        reopened = Journal(self.path)
        self.assertEqual([r["seq"] for r in reopened.replay()], [4, 5])
        self.assertEqual(reopened.last_seq, 5)

    def test_unknown_record_version_is_not_trusted(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"00000000 {}\n")
        j = Journal(self.path)
        self.assertEqual(j.replay(), [])


if __name__ == "__main__":
    unittest.main()
