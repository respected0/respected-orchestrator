"""IPC face of the voice session (B4-06). One push-to-talk session per engine connection; the renderer streams PCM, the engine keeps it in memory only.

The renderer owns the OS microphone prompt and tells us its state with each call; `voice_enabled` is read from the settings file every time, so a
switch-off takes effect on the next chunk. Nothing here confirms, approves or starts anything: the result is a *draft* the person edits."""
import base64
import binascii
from collections.abc import Callable
from typing import Any

from . import voice, winproc

MAX_CHUNK_BYTES = 48 * 1024  # decoded; a base64 chunk plus the JSON envelope stays under the 64 KiB request limit
LANGS = ("tr", "en")


class VoiceApi:
    def __init__(self, read_settings: Callable[[], dict[str, Any]], *, run: Callable[..., Any] = winproc.run, clock: Callable[[], float] | None = None):
        self._read, self._run = read_settings, run
        self._settings: dict[str, Any] = {}
        self._mic = voice.UNKNOWN
        self.session = voice.Session(self._settings, lambda: self._mic, **({"clock": clock} if clock else {}))

    def _refresh(self, permission: Any = None) -> None:
        fresh = self._read()
        self._settings.clear()
        self._settings.update({"voice_enabled": fresh.get("voice_enabled") is True})
        if permission is not None:
            self._mic = permission if permission in (voice.GRANTED, voice.DENIED) else voice.UNKNOWN

    def _engine(self):
        import json
        raw = self._read().get("voice_engine_command") or ""
        try:
            argv = json.loads(raw) if isinstance(raw, str) and raw.strip() else None
        except ValueError as error:
            raise voice.VoiceError("BAD_ENGINE", "voice_engine_command must be a JSON list of strings") from error
        return voice.command_engine(argv, self._run)

    def status(self) -> dict[str, Any]:
        self._refresh()
        try:
            engine_ready = self._engine() is not None
        except voice.VoiceError:
            engine_ready = False
        return {"enabled": bool(self._settings.get("voice_enabled")), "engine_ready": engine_ready, "state": self.session.state,
                "audio_bytes_held": self.session.audio_bytes_held, "closed_reason": self.session.closed_reason,
                "max_seconds": voice.MAX_SECONDS, "sample_rate": voice.SAMPLE_RATE, "network_isolated": False}

    def start(self, permission: Any) -> dict[str, Any]:
        self._refresh(permission)
        token = self.session.arm()
        self.session.start(token)
        return {"token": token, "sample_rate": voice.SAMPLE_RATE, "max_seconds": voice.MAX_SECONDS}

    def feed(self, token: Any, chunk: Any, permission: Any) -> dict[str, Any]:
        self._refresh(permission)
        if not isinstance(token, str) or not isinstance(chunk, str):
            raise voice.VoiceError("BAD_CHUNK", "token and chunk must be strings")
        try:
            data = base64.b64decode(chunk, validate=True)
        except (binascii.Error, ValueError) as error:
            self.session.wipe()
            raise voice.VoiceError("BAD_CHUNK", "the audio chunk is not valid base64; the recording was discarded") from error
        if len(data) > MAX_CHUNK_BYTES:
            self.session.wipe()
            raise voice.VoiceError("TOO_LARGE", "an audio chunk exceeds its limit; the recording was discarded")
        self.session.feed(token, data)
        return {"held": self.session.audio_bytes_held}

    def stop(self, token: Any, language: Any, vocabulary: Any) -> dict[str, Any]:
        self._refresh()
        if language not in LANGS:
            self.session.wipe()
            raise voice.VoiceError("BAD_LANGUAGE", "language must be tr or en")
        terms = [t for t in vocabulary if isinstance(t, str)][:200] if isinstance(vocabulary, list) else []
        audio = self.session.stop(token)
        try:
            transcript = voice.transcribe(self._engine(), audio, language, terms)
        finally:
            audio = b""  # the bytes are only ever in this frame; nothing else holds them
        return voice.to_draft(transcript, terms, language=language)

    def cancel(self) -> dict[str, Any]:
        self.session.wipe()
        return {"state": self.session.state, "audio_bytes_held": self.session.audio_bytes_held}
