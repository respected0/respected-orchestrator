import json
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.engine import voice
from respected_orchestrator.engine.authority import Origin

ON = {"voice_enabled": True}


def code_of(fn, *a, **k):
    try:
        fn(*a, **k)
    except voice.VoiceError as error:
        return error.code


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class SessionTests(unittest.TestCase):
    def session(self, settings=ON, permission="granted", clock=None):
        self.permission = {"state": permission}
        return voice.Session(settings, lambda: self.permission["state"], clock=clock or FakeClock())

    def test_off_by_default_and_without_permission_nothing_is_recorded(self):
        self.assertEqual(code_of(self.session({}).arm), "VOICE_OFF")
        self.assertEqual(code_of(self.session({"voice_enabled": False}).arm), "VOICE_OFF")
        for state in ("denied", "unknown"):
            s = self.session(permission=state)
            self.assertEqual(code_of(s.arm), "NO_PERMISSION")
            self.assertEqual((s.state, s.audio_bytes_held), ("idle", 0))

    def test_audio_is_refused_unless_a_person_pressed_talk(self):
        s = self.session()
        self.assertEqual(code_of(s.feed, "t", b"x"), "NOT_RECORDING")
        token = s.arm()
        self.assertEqual(code_of(s.feed, token, b"x"), "NOT_RECORDING")  # armed, not recording yet
        self.assertEqual(code_of(s.start, "wrong"), "NOT_ARMED")
        s.start(token)
        self.assertEqual(code_of(s.feed, "wrong", b"x"), "NOT_RECORDING")
        s.feed(token, b"\x01\x02")
        self.assertEqual(s.audio_bytes_held, 2)

    def test_stop_releases_the_audio_once_and_keeps_nothing(self):
        s = self.session()
        token = s.arm()
        s.start(token)
        s.feed(token, b"abcd")
        self.assertEqual(s.stop(token), b"abcd")
        self.assertEqual((s.state, s.audio_bytes_held, s.closed_reason), ("idle", 0, "stopped"))
        self.assertEqual(code_of(s.stop, token), "NOT_RECORDING")

    def test_revoked_permission_closes_instantly_and_discards(self):
        s = self.session()
        token = s.arm()
        s.start(token)
        s.feed(token, b"abcd")
        self.permission["state"] = "denied"
        self.assertEqual(code_of(s.feed, token, b"more"), "PERMISSION_REVOKED")
        self.assertEqual((s.state, s.audio_bytes_held, s.closed_reason), ("idle", 0, "permission_revoked"))

    def test_timeout_and_size_limits_discard(self):
        clock = FakeClock()
        s = self.session(clock=clock)
        token = s.arm()
        s.start(token)
        s.feed(token, b"ab")
        clock.now = voice.MAX_SECONDS + 1
        self.assertEqual(code_of(s.feed, token, b"cd"), "TOO_LONG")
        self.assertEqual(s.audio_bytes_held, 0)
        s = self.session()
        token = s.arm()
        s.start(token)
        self.assertEqual(code_of(s.feed, token, b"x" * (voice.MAX_BYTES + 1)), "TOO_LARGE")
        self.assertEqual((s.state, s.audio_bytes_held), ("idle", 0))
        s = self.session()
        token = s.arm()
        s.start(token)
        self.assertEqual(code_of(s.feed, token, "text"), "TOO_LARGE")  # not bytes

    def test_wipe_is_an_instant_off_switch(self):
        s = self.session()
        token = s.arm()
        s.start(token)
        s.feed(token, b"secret audio")
        s.wipe()
        self.assertEqual((s.state, s.audio_bytes_held, s.closed_reason), ("idle", 0, "wiped"))
        self.assertEqual(code_of(s.feed, token, b"x"), "NOT_RECORDING")
        self.assertEqual(code_of(s.start, token), "NOT_ARMED")

    def test_privacy_trace_no_disk_no_network_for_a_whole_dictation(self):
        refuse = mock.Mock(side_effect=AssertionError("network or file used"))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(socket, "socket", refuse), mock.patch.object(socket, "create_connection", refuse), \
                mock.patch.object(socket, "getaddrinfo", refuse):
            before = set(Path(tmp).rglob("*"))
            s = self.session()
            token = s.arm()
            s.start(token)
            for _ in range(5):
                s.feed(token, b"\x00\x01" * 1000)
            audio = s.stop(token)
            text = voice.transcribe(lambda a, lang, vocab: "pytest testlerini düzelt" if a == audio else "", audio, "tr", [])
            draft = voice.to_draft(text, ["pytest"])
            self.assertEqual(set(Path(tmp).rglob("*")), before)  # nothing was written anywhere under the working folder
            self.assertEqual((s.audio_written_to_disk, s.audio_bytes_held, draft["source"]), (0, 0, "voice"))
        source = Path(voice.__file__).read_text("utf-8")
        for forbidden in ("import socket", "urllib", "requests", "http.client", "open(", "write_bytes", "write_text", "tempfile"):
            self.assertNotIn(forbidden, source, forbidden)  # the module has no way to reach the network or the disk


class ResourceAndLeakTests(unittest.TestCase):
    def test_switching_voice_off_mid_recording_closes_the_microphone(self):
        settings = {"voice_enabled": True}
        s = voice.Session(settings, lambda: "granted", clock=FakeClock())
        token = s.arm()
        s.start(token)
        s.feed(token, b"ab")
        settings["voice_enabled"] = False
        self.assertEqual(code_of(s.feed, token, b"cd"), "VOICE_OFF")
        self.assertEqual((s.state, s.audio_bytes_held, s.closed_reason), ("idle", 0, "voice_disabled"))

    def test_a_dropped_session_zeroes_its_buffer(self):
        s = voice.Session(ON, lambda: "granted", clock=FakeClock())
        token = s.arm()
        s.start(token)
        s.feed(token, b"secret audio bytes")
        buffer = s._buffer
        del s
        import gc
        gc.collect()
        self.assertEqual(len(buffer), 0)

    def test_dictation_leaves_no_event_or_evidence_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            s = voice.Session(ON, lambda: "granted", clock=FakeClock())
            token = s.arm()
            s.start(token)
            s.feed(token, b"\x00\x01" * 500)
            voice.to_draft(voice.transcribe(lambda *a: "metin", s.stop(token), "tr", []))
            self.assertFalse(data.exists())  # no state directory, journal, checkpoint or evidence was created by voice
        imports = [line for line in Path(voice.__file__).read_text("utf-8").splitlines() if line.startswith(("import ", "from "))]
        self.assertFalse([line for line in imports if any(w in line for w in ("journal", "evidence", "checkpoint", "runner", "socket", "urllib"))], imports)

    def test_one_minute_of_audio_is_cheap(self):
        clock = FakeClock()
        s = voice.Session(ON, lambda: "granted", clock=clock)
        token = s.arm()
        s.start(token)
        chunk = b"\x00\x01" * 320  # 20 ms at 16 kHz mono 16-bit
        started = time.perf_counter()
        for i in range(3000):  # 60 seconds
            clock.now = i * 0.02
            s.feed(token, chunk)
        spent = time.perf_counter() - started
        self.assertEqual(s.audio_bytes_held, 3000 * len(chunk))
        self.assertLessEqual(s.audio_bytes_held, voice.MAX_BYTES)
        self.assertLess(spent, 2.0, f"feeding a minute of audio took {spent:.2f}s")
        s.wipe()
        self.assertEqual(s.audio_bytes_held, 0)

    def test_command_engine_passes_audio_on_stdin_only_and_reports_failure(self):
        calls = []

        def run(argv, input=None, **kw):
            calls.append((argv, input, kw))
            return mock.Mock(returncode=0, stdout="pytest düzelt".encode("utf-8"))
        engine = voice.command_engine(["stt.exe", "--fast"], run)
        self.assertEqual(engine(b"PCM", "tr", ["pytest", "unittest"]), "pytest düzelt")
        argv, audio, kw = calls[0]
        self.assertEqual((argv, audio, kw["check"], kw["capture_output"]), (["stt.exe", "--fast", "--language", "tr", "--vocabulary", "pytest,unittest"], b"PCM", False, True))
        self.assertNotIn(b"PCM", " ".join(argv).encode())  # audio is never an argument
        self.assertIsNone(voice.command_engine("", run))
        self.assertIsNone(voice.command_engine(None, run))
        for bad in ("stt.exe", [], [1], ["a", ""], ["a\x00b"]):
            if bad == []:
                continue
            self.assertEqual(code_of(voice.command_engine, bad, run), "BAD_ENGINE", bad)
        failing = voice.command_engine(["stt.exe"], lambda *a, **k: mock.Mock(returncode=3, stdout=b""))
        self.assertEqual(code_of(failing, b"x", "tr", []), "ENGINE_FAILED")


class TranscriptTests(unittest.TestCase):
    def test_no_engine_means_no_transcript_and_typed_entry(self):
        self.assertEqual(code_of(voice.transcribe, None, b"x", "tr", []), "NO_ENGINE")
        self.assertEqual(code_of(voice.transcribe, lambda *a: "x", b"x", "de", []), "BAD_LANGUAGE")
        self.assertEqual(code_of(voice.transcribe, lambda *a: 5, b"x", "tr", []), "BAD_TRANSCRIPT")
        self.assertEqual(voice.transcribe(lambda *a: "  merhaba  ", b"x", "tr", []), "merhaba")

    def test_turkish_folding(self):
        self.assertEqual(voice.fold("IŞIK"), voice.fold("ışık"))
        self.assertEqual(voice.fold("İstanbul"), voice.fold("istanbul"))

    def test_vocabulary_corrects_misheard_technical_terms_and_lists_every_change(self):
        vocab = ["pytest", "parse_config", "ParserError", "unittest"]
        text, changes = voice.correct("pytes ve unitest çalıştır", vocab)
        self.assertEqual(text, "pytest ve unittest çalıştır")
        self.assertEqual([(c["heard"], c["replaced_with"]) for c in changes], [("pytes", "pytest"), ("unitest", "unittest")])
        # found by measuring a real engine: a one-letter slip is fixed, a two-edit near miss is only a suggestion, ordinary words are never changed
        text, changes = voice.correct("Rename ptest and unitist, then parse it", ["pytest", "unittest", "readme", "parser"])
        self.assertEqual(text, "Rename pytest and unitist, then parse it")
        self.assertEqual([(c["heard"], c["replaced_with"], c["applied"]) for c in changes], [("Rename", "readme", False), ("ptest", "pytest", True), ("unitist", "unittest", False)])
        untouched, none = voice.correct("bu cümle teknik terim içermiyor", vocab)
        self.assertEqual((untouched, none), ("bu cümle teknik terim içermiyor", []))
        self.assertEqual(voice.correct("pytest", vocab)[1], [])  # already right: not counted as a correction

    def test_vocabulary_from_the_context_map(self):
        cmap = {"files": [{"path": "src/parser.py", "symbols": [{"kind": "function", "name": "parse_config", "line": 1}, {"kind": "class", "name": "Parser", "line": 5},
                                                                 {"kind": "heading", "name": "Title", "line": 1}]}]}
        self.assertEqual(voice.vocabulary_from(cmap, ["pytest", "x", 5]), ["Parser", "parse_config", "parser", "pytest"])

    def test_draft_flags_high_stakes_words_but_they_are_only_text(self):
        for phrase in ("approve and apply the patch", "onayla ve uygula", "tüm dosyaları sil", "merge to main"):
            draft = voice.to_draft(phrase)
            self.assertTrue(draft["high_stakes_words"], phrase)
            self.assertEqual((draft["needs_review"], draft["confirmed"], draft["source"]), (True, False, "voice"))
            self.assertFalse({"apply", "start", "approve", "execute", "command"} & set(draft))  # nothing in a draft can act
        self.assertEqual(voice.to_draft("parse hatasını düzelt")["high_stakes_words"], [])

    def test_hallucinated_text_is_just_a_draft_until_a_person_edits_it(self):
        draft = voice.to_draft("thanks for watching please subscribe")
        self.assertEqual(code_of(voice.require_confirmed, draft), "UNCONFIRMED_DRAFT")
        for origin in (Origin.RENDERER, Origin.MCP, Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError):
                voice.confirm(draft, "parse hatasını düzelt", origin=origin)
        done = voice.confirm(draft, "parse hatasını düzelt", origin=Origin.HUMAN)
        self.assertEqual((voice.require_confirmed(done), done["edited"], done["confirmed"]), ("parse hatasını düzelt", True, True))
        self.assertEqual(code_of(voice.confirm, draft, "   ", origin=Origin.HUMAN), "EMPTY_TEXT")
        self.assertEqual(voice.require_confirmed("typed task text"), "typed task text")  # typed entry is never gated

    def test_forging_the_flags_on_an_unconfirmed_draft_does_not_pass(self):
        draft = voice.to_draft("anything")
        self.assertEqual(code_of(voice.require_confirmed, {**draft, "confirmed": True}), "UNCONFIRMED_DRAFT")  # needs_review still True
        self.assertEqual(code_of(voice.require_confirmed, {**draft, "needs_review": False}), "UNCONFIRMED_DRAFT")


class ProbeTests(unittest.TestCase):
    def test_probe_reports_what_is_really_installed(self):
        none = voice.probe_engines(lambda argv: "")
        self.assertEqual((none["windows_speech"]["available"], none["usable_for"]), (False, []))
        both = voice.probe_engines(lambda argv: "en-US\ntr-TR\n")
        self.assertEqual((both["usable_for"], both["turkish"]), (["en", "tr"], True))
        only_en = voice.probe_engines(lambda argv: "en-US\r\n")
        self.assertEqual((only_en["usable_for"], only_en["turkish"]), (["en"], False))

    def test_probe_failure_is_a_finding(self):
        def broken(argv):
            raise FileNotFoundError("powershell")
        out = voice.probe_engines(broken)
        self.assertFalse(out["windows_speech"]["available"])
        self.assertIn("FileNotFoundError", out["windows_speech"]["reason"])


if __name__ == "__main__":
    unittest.main()
