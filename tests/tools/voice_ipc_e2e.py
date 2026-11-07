"""Manual evidence run (not part of unittest discovery): real clips -> voice.* IPC -> real faster-whisper -> draft. Usage: python -m tests.tools.voice_ipc_e2e OUT.json STT_DIR."""
import base64
import json
import sys
import tempfile
import wave
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import local_api

STT = Path(sys.argv[2])  # the tests package redirects the home folder, so the real one is passed in
PY, SCRIPT = str(STT / "venv/Scripts/python.exe"), str(Path(__file__).resolve().parents[2] / "packaging/voice/faster_whisper_stt.py")
n = [0]


def main(out: str) -> None:
    temp = tempfile.TemporaryDirectory()
    ctx = EngineContext(Path(temp.name).resolve() / "data")
    ctx.data_root.mkdir(parents=True, exist_ok=True)
    (ctx.data_root / "settings.json").write_text(json.dumps({"voice_enabled": True, "voice_engine_command": json.dumps([PY, "-I", SCRIPT])}), "utf-8")
    api = local_api.LocalApi(ctx, "tok-0123456789abcdef")

    def call(cmd, payload=None):
        n[0] += 1
        return api.handle({"ipc": local_api.IPC, "id": f"req-{n[0]:08}", "session": "tok-0123456789abcdef", "cmd": cmd, "payload": payload or {}})

    results = []
    for clip in sorted((STT / "samples").glob("*.wav")):
        with wave.open(str(clip)) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2), clip
            pcm = w.readframes(w.getnframes())
        token = call("voice.start", {"permission": "granted"})["result"]["token"]
        for i in range(0, len(pcm), 32 * 1024):
            r = call("voice.feed", {"token": token, "chunk": base64.b64encode(pcm[i:i + 32 * 1024]).decode(), "permission": "granted"})
            assert r["ok"], r
        draft = call("voice.stop", {"token": token, "language": "en", "vocabulary": ["pytest", "parse_config", "unittest", "readme"]})
        results.append({"clip": clip.stem, "ok": draft["ok"], "text": (draft["result"] or {}).get("text"), "needs_review": (draft["result"] or {}).get("needs_review"),
                        "confirmed": (draft["result"] or {}).get("confirmed"), "audio_bytes_held_after": call("voice.status")["result"]["audio_bytes_held"]})
    Path(out).write_text(json.dumps(results, indent=1, ensure_ascii=False), "utf-8")
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
