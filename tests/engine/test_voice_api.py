"""Push-to-talk over the IPC server (B4-06): permission, chunking, wipe on every refusal, draft-only result, no audio left behind."""
import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import local_api, voice

PCM = bytes(range(256)) * 40
FAKE_STT = "import sys; sys.stdin.buffer.read(); print('fix the parse config and run ptest')"


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ctx = EngineContext(Path(temp.name).resolve() / "data")
        self.ctx.data_root.mkdir(parents=True, exist_ok=True)
        self.api = local_api.LocalApi(self.ctx, "tok-0123456789abcdef")
        self.n = 0

    def settings(self, **values):
        (self.ctx.data_root / "settings.json").write_text(json.dumps(values), "utf-8")

    def call(self, cmd, payload=None):
        self.n += 1
        return self.api.handle({"ipc": local_api.IPC, "id": f"req-{self.n:08}", "session": "tok-0123456789abcdef", "cmd": cmd, "payload": payload or {}})

    def on(self):
        self.settings(voice_enabled=True, voice_engine_command=json.dumps([sys.executable, "-c", FAKE_STT]))


class VoiceIpcTests(Base):
    def test_commands_and_authority(self):
        self.assertEqual(local_api.COMMANDS["voice.status"][1].value, "read")
        for cmd in ("voice.start", "voice.feed", "voice.stop", "voice.cancel"):
            self.assertEqual(local_api.COMMANDS[cmd][1].value, "task", cmd)
        self.assertFalse(any("approve" in c or "confirm" in c for c in local_api.COMMANDS if c.startswith("voice.")))

    def test_off_by_default_nothing_starts(self):
        status = self.call("voice.status")["result"]
        self.assertEqual((status["enabled"], status["engine_ready"], status["state"]), (False, False, "idle"))
        out = self.call("voice.start", {"permission": "granted"})
        self.assertIn("VOICE_OFF", out["error"]["message"])

    def test_no_permission_no_recording(self):
        self.on()
        for state in ("denied", None, "bogus"):
            out = self.call("voice.start", {"permission": state})
            self.assertIn("NO_PERMISSION", out["error"]["message"], state)
        self.assertEqual(self.call("voice.status")["result"]["state"], "idle")

    def test_full_push_to_talk_returns_an_unconfirmed_draft_and_leaves_no_audio(self):
        self.on()
        token = self.call("voice.start", {"permission": "granted"})["result"]["token"]
        for _ in range(3):
            out = self.call("voice.feed", {"token": token, "chunk": base64.b64encode(PCM).decode(), "permission": "granted"})
            self.assertTrue(out["ok"], out)
        self.assertEqual(self.call("voice.status")["result"]["audio_bytes_held"], 3 * len(PCM))
        draft = self.call("voice.stop", {"token": token, "language": "en", "vocabulary": ["pytest", "parse_config"]})["result"]
        self.assertEqual((draft["source"], draft["needs_review"], draft["confirmed"]), ("voice", True, False))
        self.assertIn("pytest", draft["text"])
        self.assertTrue(any(c["heard"] == "ptest" and c["applied"] for c in draft["corrections"]))
        self.assertEqual(self.call("voice.status")["result"]["audio_bytes_held"], 0)
        self.assertEqual(sorted(p.name for p in self.ctx.data_root.rglob("*") if p.suffix in (".wav", ".pcm", ".raw")), [])
        with self.assertRaises(voice.VoiceError):
            voice.require_confirmed(draft)  # speech alone never reaches plan/start

    def test_revoked_permission_or_switch_off_discards_the_audio_at_once(self):
        self.on()
        token = self.call("voice.start", {"permission": "granted"})["result"]["token"]
        self.call("voice.feed", {"token": token, "chunk": base64.b64encode(PCM).decode(), "permission": "granted"})
        out = self.call("voice.feed", {"token": token, "chunk": base64.b64encode(PCM).decode(), "permission": "denied"})
        self.assertIn("PERMISSION_REVOKED", out["error"]["message"])
        self.assertEqual(self.call("voice.status")["result"]["audio_bytes_held"], 0)
        token = self.call("voice.start", {"permission": "granted"})["result"]["token"]
        self.settings(voice_enabled=False)
        self.assertIn("VOICE_OFF", self.call("voice.feed", {"token": token, "chunk": base64.b64encode(PCM).decode(), "permission": "granted"})["error"]["message"])
        self.assertEqual(self.call("voice.status")["result"]["state"], "idle")

    def test_bad_chunks_wrong_tokens_and_oversize_are_dropped(self):
        self.on()
        token = self.call("voice.start", {"permission": "granted"})["result"]["token"]
        self.assertFalse(self.call("voice.feed", {"token": "nope", "chunk": "AAAA", "permission": "granted"})["ok"])
        self.assertIn("BAD_CHUNK", self.call("voice.feed", {"token": token, "chunk": "!!not base64!!", "permission": "granted"})["error"]["message"])
        self.assertEqual(self.call("voice.status")["result"]["state"], "idle")
        token = self.call("voice.start", {"permission": "granted"})["result"]["token"]
        big = base64.b64encode(bytes(voice_api_limit() + 1)).decode()
        self.assertIn("TOO_LARGE", self.call("voice.feed", {"token": token, "chunk": big, "permission": "granted"})["error"]["message"])
        self.assertEqual(self.call("voice.status")["result"]["audio_bytes_held"], 0)

    def test_cancel_is_instant_and_no_engine_means_typed_entry(self):
        self.settings(voice_enabled=True)
        token = self.call("voice.start", {"permission": "granted"})["result"]["token"]
        self.call("voice.feed", {"token": token, "chunk": base64.b64encode(PCM).decode(), "permission": "granted"})
        self.assertIn("NO_ENGINE", self.call("voice.stop", {"token": token, "language": "tr", "vocabulary": []})["error"]["message"])
        self.assertEqual(self.call("voice.status")["result"]["audio_bytes_held"], 0)
        token = self.call("voice.start", {"permission": "granted"})["result"]["token"]
        self.call("voice.feed", {"token": token, "chunk": base64.b64encode(PCM).decode(), "permission": "granted"})
        self.assertEqual(self.call("voice.cancel")["result"], {"state": "idle", "audio_bytes_held": 0})

    def test_unsupported_language_is_refused_and_wipes(self):
        self.on()
        token = self.call("voice.start", {"permission": "granted"})["result"]["token"]
        self.call("voice.feed", {"token": token, "chunk": base64.b64encode(PCM).decode(), "permission": "granted"})
        self.assertIn("BAD_LANGUAGE", self.call("voice.stop", {"token": token, "language": "xx"})["error"]["message"])
        self.assertEqual(self.call("voice.status")["result"]["audio_bytes_held"], 0)

    def test_worker_origin_cannot_use_voice(self):
        api = local_api.LocalApi(self.ctx, "tok-0123456789abcdef", origin=local_api.Origin.WORKER)
        out = api.handle({"ipc": local_api.IPC, "id": "req-00000099", "session": "tok-0123456789abcdef", "cmd": "voice.status", "payload": {}})
        self.assertEqual(out["error"]["code"], "FORBIDDEN")


def voice_api_limit():
    from respected_orchestrator.engine import voice_api
    return voice_api.MAX_CHUNK_BYTES


if __name__ == "__main__":
    unittest.main()
