import re
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import attachment as at
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.evidence import save_signed

HUMAN = Origin.HUMAN
RUN = "run-20261108000000-abcdef123456"


def chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def png(width=8, height=4, extra=(), rect=None):
    rows = b""
    # A header can claim any size; only the pixel rows are real, so a "huge" image costs nothing to build (rows stop at 64x64).
    for y in range(min(height, 64)):
        rows += b"\x00" + b"".join(b"\x00\x00\x00" if rect and rect[0] <= x < rect[2] and rect[1] <= y < rect[3] else b"\xc8\xc8\xc8" for x in range(min(width, 64)))
    parts = [at.PNG_SIG, chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))]
    parts += [chunk(k, b) for k, b in extra]
    parts += [chunk(b"IDAT", zlib.compress(rows)), chunk(b"IEND", b"")]
    return b"".join(parts)


def jpeg(width=16, height=8, with_exif=True):
    seg = lambda marker, body: bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body
    out = b"\xff\xd8" + seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    if with_exif:
        out += seg(0xE1, b"Exif\x00\x00GPS 41.0082N 28.9784E camera=Secret") + seg(0xFE, b"comment with secret")
    out += seg(0xC0, b"\x08" + struct.pack(">HH", height, width) + b"\x01\x01\x11\x00")
    out += seg(0xDA, b"\x01\x01\x00\x00\x3f\x00") + b"\x12\x34\x56" + b"\xff\xd9"
    return out


def code_of(fn, *a, **k):
    try:
        fn(*a, **k)
    except at.AttachError as error:
        return error.code


class InspectTests(unittest.TestCase):
    def test_png_metadata_is_stripped_and_the_picture_is_untouched(self):
        dirty = png(extra=[(b"tEXt", b"Comment\x00my password is hunter2"), (b"eXIf", b"GPS"), (b"tIME", b"\x07\xea\x0b\x08\x00\x00\x00"), (b"zzZz", b"private chunk")])
        info = at.inspect(dirty)
        self.assertEqual((info["mime"], info["width"], info["height"]), ("image/png", 8, 4))
        for secret in (b"hunter2", b"GPS", b"private chunk", b"tEXt", b"eXIf"):
            self.assertNotIn(secret, info["clean"])
        self.assertEqual(info["clean"], png())  # byte-identical to the same image built without metadata
        self.assertGreater(info["metadata_removed"], 0)
        self.assertEqual(at.inspect(info["clean"])["sha256"], info["sha256"])  # cleaning is idempotent

    def test_jpeg_exif_xmp_and_comments_are_stripped(self):
        info = at.inspect(jpeg())
        self.assertEqual((info["mime"], info["width"], info["height"]), ("image/jpeg", 16, 8))
        for secret in (b"GPS", b"Secret", b"comment with secret", b"Exif"):
            self.assertNotIn(secret, info["clean"])
        self.assertIn(b"JFIF", info["clean"])
        self.assertEqual(info["clean"], jpeg(with_exif=False))

    def test_refused_formats_and_bad_files(self):
        cases = {"BAD_FORMAT": [b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", b"GIF89a....", b"RIFF\x00\x00\x00\x00WEBPVP8 ", b"%PDF-1.7", b"MZ\x90\x00", b"plain text"],
                 "EMPTY": [b"", None, "text"], "MALFORMED": [at.PNG_SIG + b"junk", png()[:-20], b"\xff\xd8\xff\xe0\x00\x10JFIF", b"\xff\xd8\xff\xd9"]}
        for code, items in cases.items():
            for item in items:
                self.assertEqual(code_of(at.inspect, item), code, item)

    def test_huge_images_and_bad_chunk_lengths(self):
        self.assertEqual(code_of(at.inspect, png(width=100000, height=100000)), "TOO_BIG")
        self.assertEqual(code_of(at.inspect, png(width=7000, height=7000)), "TOO_BIG")  # inside the side limit but over the pixel limit
        self.assertEqual(code_of(at.inspect, b"\xff\xd8\xff" + b"\x00" * (at.MAX_BYTES + 1)), "TOO_LARGE")
        lying = at.PNG_SIG + struct.pack(">I", 2**31) + b"IHDR" + b"\x00" * 20
        self.assertEqual(code_of(at.inspect, lying), "MALFORMED")


class CaptureTests(unittest.TestCase):
    def make(self, settings=None, permission="granted", clock=None):
        self.perm = {"v": permission}
        self.now = {"v": 0.0}
        return at.CaptureSession({"screenshot_enabled": True} if settings is None else settings, lambda: self.perm["v"], clock=clock or (lambda: self.now["v"]))

    def test_off_by_default_and_no_permission_means_no_image(self):
        self.assertEqual(code_of(self.make({}).arm), "CAPTURE_OFF")
        for state in ("denied", "unknown", "prompt"):
            self.assertEqual(code_of(self.make(permission=state).arm), "NO_PERMISSION")

    def test_nothing_is_accepted_unless_a_person_armed_it(self):
        s = self.make()
        self.assertEqual(code_of(s.submit, "t", png()), "NOT_ARMED")  # background capture does not exist
        token = s.arm()
        self.assertEqual(code_of(s.submit, "wrong", png()), "NOT_ARMED")
        info = s.submit(token, png(), {"monitor": 1, "dpi_scale": 1.5})
        self.assertEqual((info["width"], info["monitor"], info["dpi_scale"], s.state), (8, 1, 1.5, "idle"))
        self.assertEqual(code_of(s.submit, token, png()), "NOT_ARMED")  # one image per press

    def test_cancel_mid_capture_and_failures_discard(self):
        s = self.make()
        token = s.arm()
        s.cancel()
        self.assertEqual((s.state, s.closed_reason, code_of(s.submit, token, png())), ("idle", "cancelled", "NOT_ARMED"))
        for bad, code in ((b"not an image", "BAD_FORMAT"), (png(width=100000, height=100000), "TOO_BIG")):
            token = s.arm()
            self.assertEqual(code_of(s.submit, token, bad), code)
            self.assertEqual(s.state, "idle")

    def test_revoked_permission_and_expiry_and_bad_meta(self):
        s = self.make()
        token = s.arm()
        self.perm["v"] = "denied"
        self.assertEqual(code_of(s.submit, token, png()), "PERMISSION_REVOKED")
        self.perm["v"] = "granted"
        token = s.arm()
        self.now["v"] = 1000
        self.assertEqual(code_of(s.submit, token, png()), "EXPIRED")
        for meta in ({"monitor": -1}, {"monitor": "0"}, {"dpi_scale": 0}, {"dpi_scale": True}, {"dpi_scale": 99}):
            token = s.arm()
            self.assertEqual(code_of(s.submit, token, png(), meta), "BAD_META", meta)

    def test_multi_monitor_indexes_are_just_labels(self):
        s = self.make()
        self.assertEqual(s.submit(s.arm(), png(), {"monitor": 3})["monitor"], 3)


class StoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ctx = EngineContext(Path(temp.name).resolve() / "data")
        self.image = png(extra=[(b"tEXt", b"Comment\x00secret")], rect=(2, 1, 5, 3))
        self.digest = at.inspect(self.image)["sha256"]
        self.queue(RUN)

    def queue(self, run_id, status="queued"):
        directory = self.ctx.run_dir(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        save_signed(self.ctx, directory / "status.json", {"run_id": run_id, "status": status})

    def attach(self, **kw):
        return at.attach(self.ctx, kw.pop("run", RUN), kw.pop("image", self.image), kw.pop("digest", self.digest), origin=kw.pop("origin", HUMAN), **kw)

    def test_preview_is_mandatory_and_bound_to_the_exact_bytes(self):
        self.assertEqual(code_of(self.attach, digest="0" * 64), "PREVIEW_REQUIRED")
        self.assertEqual(code_of(self.attach, image=png(width=9)), "PREVIEW_REQUIRED")  # a different picture than the one previewed
        self.assertEqual(code_of(self.attach, digest=None), "PREVIEW_REQUIRED")
        record = self.attach(redacted_regions=2)
        self.assertEqual((record["visibility"], record["shared_with_model"], record["redacted_regions"], record["sha256"]), ("task_only", False, 2, self.digest))
        self.assertEqual(code_of(self.attach, redacted_regions=-1), "BAD_META")

    def test_only_a_human_attaches(self):
        for origin in (Origin.RENDERER, Origin.MCP, Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError):
                self.attach(origin=origin)

    def test_wrong_run_bad_ids_and_path_traversal(self):
        self.queue("run-20261108000001-aaaaaaaaaaaa", "completed")
        self.assertEqual(code_of(self.attach, run="run-20261108000001-aaaaaaaaaaaa"), "WRONG_RUN")  # already ran
        self.assertEqual(code_of(self.attach, run="run-20261108000002-bbbbbbbbbbbb"), "WRONG_RUN")  # does not exist
        for evil in ("../../etc", "..\\x", "run-1/../../x", ""):
            self.assertEqual(code_of(self.attach, run=evil), "WRONG_RUN", evil)
        att = self.attach()["id"]
        for evil in ("../x", "att-../../..", "att-", att + "x", "ATT-" + att[4:]):
            self.assertEqual(code_of(at.read_for_person, self.ctx, RUN, evil, origin=HUMAN), "BAD_ID", evil)

    def test_stored_image_is_clean_and_belongs_only_to_its_run(self):
        record = self.attach()
        stored, data = at.read_for_person(self.ctx, RUN, record["id"], origin=HUMAN)
        self.assertNotIn(b"secret", data)
        self.assertEqual((stored["run_id"], len(data)), (RUN, stored["bytes"]))
        other = "run-20261108000003-cccccccccccc"
        self.queue(other)
        self.assertEqual(code_of(at.read_for_person, self.ctx, other, record["id"], origin=HUMAN), "NOT_FOUND")  # not visible from another run

    def test_third_parties_cannot_read(self):
        record = self.attach()
        for origin in (Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError):
                at.read_for_person(self.ctx, RUN, record["id"], origin=origin)

    def test_tampering_and_expiry_are_detected(self):
        record = self.attach()
        directory = self.ctx.run_dir(RUN) / "attachments"
        self.assertEqual(code_of(at.read_for_person, self.ctx, RUN, record["id"], origin=HUMAN, now=record["expires_at"] + 1), "EXPIRED")
        (directory / f"{record['id']}.bin").write_bytes(png(width=2))
        self.assertEqual(code_of(at.read_for_person, self.ctx, RUN, record["id"], origin=HUMAN), "TAMPERED")
        (directory / f"{record['id']}.json").write_text('{"payload": {"expires_at": 9e18}, "signature": "x"}')
        self.assertEqual(code_of(at.read_for_person, self.ctx, RUN, record["id"], origin=HUMAN), "NOT_FOUND")  # a forged record does not verify

    def test_purge_and_ttl_sweep(self):
        first = self.attach(now=1000.0)
        second = self.attach(now=1000.0 + at.TTL_SECONDS)
        self.assertEqual(at.sweep(self.ctx, now=1000.0 + at.TTL_SECONDS - 1), 0)
        self.assertEqual(at.sweep(self.ctx, now=1000.0 + at.TTL_SECONDS + 1), 2)  # the first image's .json and .bin
        self.assertEqual(code_of(at.read_for_person, self.ctx, RUN, first["id"], origin=HUMAN, now=1000.0 + at.TTL_SECONDS + 1), "NOT_FOUND")
        self.assertEqual(at.read_for_person(self.ctx, RUN, second["id"], origin=HUMAN, now=1000.0 + at.TTL_SECONDS + 1)[0]["id"], second["id"])
        self.assertGreater(at.purge(self.ctx, RUN), 0)
        self.assertEqual(at.purge(self.ctx, RUN), 0)
        self.assertFalse((self.ctx.run_dir(RUN) / "attachments").exists())

    # ---- model transfer -------------------------------------------------------------------------------------------------
    def test_no_image_leaves_without_an_explicit_consent(self):
        record = self.attach()
        self.assertEqual(code_of(at.bytes_for_model, self.ctx, RUN, record["id"], "openrouter"), "NO_CONSENT")
        for origin in (Origin.RENDERER, Origin.MCP, Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError):
                at.share(self.ctx, RUN, record["id"], "openrouter", origin=origin)
        self.assertEqual(code_of(at.share, self.ctx, RUN, record["id"], "", origin=HUMAN), "BAD_PROVIDER")

    def test_consent_is_one_provider_one_image_one_run_and_short(self):
        record = self.attach()
        consent = at.share(self.ctx, RUN, record["id"], "openrouter", origin=HUMAN, now=5000.0)
        self.assertIn("outside this computer", consent["disclosure"])
        self.assertEqual(at.bytes_for_model(self.ctx, RUN, record["id"], "openrouter", now=5001.0)[:8], at.PNG_SIG)
        self.assertEqual(code_of(at.bytes_for_model, self.ctx, RUN, record["id"], "claude", now=5001.0), "CONSENT_MISMATCH")
        self.assertEqual(code_of(at.bytes_for_model, self.ctx, RUN, record["id"], "openrouter", now=5000.0 + at.CONSENT_SECONDS + 1), "EXPIRED")

    def test_revoke_mid_transfer_stops_the_next_read(self):
        record = self.attach()
        at.share(self.ctx, RUN, record["id"], "openrouter", origin=HUMAN)
        self.assertTrue(at.bytes_for_model(self.ctx, RUN, record["id"], "openrouter"))
        at.revoke(self.ctx, RUN, record["id"], origin=HUMAN)
        self.assertEqual(code_of(at.bytes_for_model, self.ctx, RUN, record["id"], "openrouter"), "REVOKED")
        with self.assertRaises(PermissionError):
            at.revoke(self.ctx, RUN, record["id"], origin=Origin.WORKER)

    def test_consent_copied_to_another_image_is_refused(self):
        a, b = self.attach(), self.attach(image=png(width=9), digest=at.inspect(png(width=9))["sha256"])
        at.share(self.ctx, RUN, a["id"], "openrouter", origin=HUMAN)
        directory = self.ctx.run_dir(RUN) / "attachments"
        (directory / f"{b['id']}.consent.json").write_bytes((directory / f"{a['id']}.consent.json").read_bytes())
        self.assertEqual(code_of(at.bytes_for_model, self.ctx, RUN, b["id"], "openrouter"), "CONSENT_MISMATCH")

    def test_purge_removes_consents_too(self):
        record = self.attach()
        at.share(self.ctx, RUN, record["id"], "openrouter", origin=HUMAN)
        at.purge(self.ctx, RUN)
        self.assertEqual(code_of(at.bytes_for_model, self.ctx, RUN, record["id"], "openrouter"), "NOT_FOUND")

    def test_nothing_else_in_the_engine_can_reach_attachment_bytes(self):
        """The only ways to read an image are read_for_person and bytes_for_model; no other module imports this one, so no log,
        evidence view, checkpoint or worker prompt can carry it (an adapter that wants it must call bytes_for_model)."""
        root = Path(at.__file__).resolve().parents[1]
        users = [p.name for p in root.rglob("*.py") if p.name != "attachment.py" and re.search(r"\battachment\b", p.read_text("utf-8")) and
                 re.search(r"(from \.+\w*\s*import[^\n]*\battachment\b|import [\w.]*attachment\b|from [\w.]*attachment import)", p.read_text("utf-8"))]
        self.assertEqual(users, [])


if __name__ == "__main__":
    unittest.main()
