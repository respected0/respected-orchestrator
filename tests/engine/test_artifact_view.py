import hashlib
import json
import os
import subprocess
import unittest

from respected_orchestrator.engine import artifact_view as av
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.journal import Journal
from respected_orchestrator.engine.local_api import LocalApi
from respected_orchestrator.engine.runner import create_task, execute_task
from tests.workflows.test_reviewer_reliability import CodingFixture


class ArtifactViewTests(CodingFixture):
    def setUp(self):
        super().setUp()
        self.run_id = create_task(self.ctx, self.request())["run_id"]
        self.assertEqual(execute_task(self.ctx, self.run_id)["status"], "completed")
        self.dir = self.ctx.run_dir(self.run_id)

    def names(self):
        return [a["name"] for a in av.list_artifacts(self.ctx, self.run_id)["artifacts"]]

    def read_all(self, name, length=av.MAX_CHUNK):
        out, offset, chunks = "", 0, 0
        while True:
            c = av.read_chunk(self.ctx, self.run_id, name, offset, length)
            out, offset, chunks = out + (c["content"] or ""), c["next_offset"], chunks + 1
            if c["eof"]:
                return out, chunks, c

    def test_listing_shows_only_the_runs_own_evidence(self):
        names = self.names()
        self.assertIn("worker.patch", names)
        self.assertIn("result.json", names)
        (self.dir / "applying").write_text("claim")
        (self.dir / ".hidden.json").write_text("x")
        (self.dir / "script.exe").write_bytes(b"MZ")
        self.assertNotIn("applying", self.names())
        self.assertNotIn(".hidden.json", self.names())
        self.assertNotIn("script.exe", self.names())

    def test_patch_reads_back_exactly_with_digest_and_audit_trail(self):
        text, _, last = self.read_all("worker.patch")
        self.assertEqual(text.encode(), (self.dir / "worker.patch").read_bytes())
        self.assertEqual(last["sha256"], hashlib.sha256((self.dir / "worker.patch").read_bytes()).hexdigest())
        events = [r for r in Journal(self.ctx.state_dir / "events.log").replay() if r["type"] == "artifact.read"]
        self.assertTrue(events)
        self.assertEqual(events[-1]["p"]["sha256"], last["sha256"])
        self.assertEqual(events[-1]["run"], self.run_id)

    def test_traversal_absolute_unlisted_and_malformed_names_are_all_refused(self):
        (self.ctx.data_root.parent / "outside.log").write_text("secret outside", encoding="utf8")
        for bad in ("../outside.log", "..\\outside.log", "artifacts/../result.json", "/etc/passwd", "C:\\Windows\\win.ini", "request.json\x00.log",
                    "nothere.log", "", None, 5, "artifacts/", "a/b/c.log", "..", "request.json/../x"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                av.read_chunk(self.ctx, self.run_id, bad)
        for bad_run in ("../x", "run-../../etc", "run-doesnotexist", None):
            with self.assertRaises(ValueError, msg=repr(bad_run)):
                av.list_artifacts(self.ctx, bad_run)

    def test_symlinks_and_junctions_are_never_followed(self):
        target = self.ctx.data_root.parent / "outside.log"
        target.write_text("TOP SECRET OUTSIDE", encoding="utf8")
        link = self.dir / "evil.log"
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            subprocess.run(["cmd", "/c", "mklink", str(link), str(target)], capture_output=True)
        if link.is_symlink():
            self.assertNotIn("evil.log", self.names())
            with self.assertRaises(ValueError):
                av.read_chunk(self.ctx, self.run_id, "evil.log")
        junction = self.dir / "artifacts"
        if os.name == "nt" and not junction.exists():
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(target.parent)], capture_output=True)
            if made.returncode == 0:
                self.assertFalse(any(n.startswith("artifacts/") for n in self.names()))
        self.assertTrue(link.is_symlink() or os.name == "nt", "could not create any link to test with")

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows reparse point")
    def test_artifacts_folder_that_is_a_junction_to_outside_leaks_nothing(self):
        outside = self.ctx.data_root.parent / "outside-dir"
        outside.mkdir()
        (outside / "leak.log").write_text("OUTSIDE SECRET", encoding="utf8")
        self.assertFalse((self.dir / "artifacts").exists())
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.dir / "artifacts"), str(outside)], capture_output=True)
        self.assertEqual(made.returncode, 0, "junction could not be created, the protection is untested")
        self.assertFalse(any(n.startswith("artifacts/") for n in self.names()))
        with self.assertRaises(ValueError):
            av.read_chunk(self.ctx, self.run_id, "artifacts/leak.log")
        subprocess.run(["cmd", "/c", "rmdir", str(self.dir / "artifacts")], capture_output=True)  # removes only the junction

    def test_file_swapped_for_a_link_after_listing_is_refused(self):
        listed = self.names()
        self.assertIn("worker.patch", listed)
        target = self.ctx.data_root.parent / "outside2.log"
        target.write_text("outside", encoding="utf8")
        (self.dir / "worker.patch").unlink()
        try:
            os.symlink(target, self.dir / "worker.patch")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not permitted for this user")
        with self.assertRaises(ValueError):
            av.read_chunk(self.ctx, self.run_id, "worker.patch")

    def test_ansi_osc_and_control_codes_are_stripped(self):
        (self.dir / "agent.log").write_bytes(b"\x1b[31mred\x1b[0m \x1b]0;pwned title\x07ok \x1b[2J\x1b[Hcleared\x08\x08 bell\x07 end\n")
        text, _, _ = self.read_all("agent.log")
        self.assertEqual(text, "red ok cleared bell end\n")

    def test_secrets_are_redacted_even_when_they_sit_on_a_chunk_boundary(self):
        secret = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2"
        body = ("filler line\n" * 40) + f"token = {secret}\n" + ("tail line\n" * 40)
        (self.dir / "leaky.log").write_text(body, encoding="utf8")
        for chunk in (7, 31, 64, 200, 1000):
            text, _, _ = self.read_all("leaky.log", length=chunk)
            self.assertNotIn(secret, text, chunk)
            self.assertNotIn("A1b2C3d4E5f6", text, chunk)

    def test_huge_and_binary_files_are_bounded_and_not_dumped(self):
        (self.dir / "huge.log").write_bytes(b"x" * (5 * 1024 * 1024))
        first = av.read_chunk(self.ctx, self.run_id, "huge.log", 0, 10 ** 9)
        self.assertLessEqual(first["next_offset"], av.MAX_CHUNK)
        self.assertFalse(first["eof"])
        self.assertEqual(first["size"], 5 * 1024 * 1024)
        (self.dir / "blob.log").write_bytes(b"\x00\x01\x02binary\xff" * 100)
        b = av.read_chunk(self.ctx, self.run_id, "blob.log")
        self.assertEqual((b["binary"], b["content"]), (True, None))
        (self.dir / "shot.png").write_bytes(b"\x89PNG not really")
        self.assertIsNone(av.read_chunk(self.ctx, self.run_id, "shot.png")["content"])

    def test_digest_is_unknown_not_guessed_above_the_limit(self):
        (self.dir / "big.log").write_bytes(b"y" * 1024)
        old = av.DIGEST_LIMIT
        av.DIGEST_LIMIT = 100
        try:
            self.assertIsNone(av.read_chunk(self.ctx, self.run_id, "big.log")["sha256"])
        finally:
            av.DIGEST_LIMIT = old

    def test_bad_offsets_and_lengths(self):
        for off, ln in ((-1, 5), (0, 0), ("0", 5), (0, 1.5), (True, 1)):
            if off is True:
                continue
            with self.assertRaises(ValueError, msg=(off, ln)):
                av.read_chunk(self.ctx, self.run_id, "worker.patch", off, ln)
        past = av.read_chunk(self.ctx, self.run_id, "worker.patch", 10 ** 6, 10)
        self.assertEqual((past["content"], past["eof"]), ("", True))

    def test_ipc_is_read_only_and_uses_the_connection_journal(self):
        journal = Journal(self.ctx.state_dir / "events.log")
        before = journal.last_seq
        api = LocalApi(self.ctx, "t" * 32, origin=Origin.MCP, journal=journal)
        call = lambda cmd, n, **p: api.handle({"ipc": "1", "id": f"art-{n:05d}", "session": "t" * 32, "cmd": cmd, "payload": p})
        listed = call("artifact.list", 1, run_id=self.run_id)
        self.assertTrue(listed["ok"] and listed["result"]["artifacts"], listed)
        got = call("artifact.read", 2, run_id=self.run_id, name="worker.patch")
        self.assertTrue(got["ok"] and "+value = 1" in got["result"]["content"], got)
        self.assertEqual(journal.last_seq, before + 1)  # the read was audited on the live journal
        self.assertEqual(call("artifact.read", 3, run_id=self.run_id, name="../x")["error"]["code"], "ENGINE_ERROR")


if __name__ == "__main__":
    unittest.main()
