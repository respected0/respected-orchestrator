"""In-app voice task drafting, engine side (B4-06). Voice is text input to a *draft*, never a command.

What this module guarantees, by construction and by test:
  * off by default (`voice_enabled`), and a recording can only start while it is enabled, the OS microphone permission is granted
    and a person pressed talk (`arm` then `start`); permission revoked, a stop, a timeout, a size limit or an error closes it at once;
  * audio lives only in a bytearray owned by the session. There is no write path: no file, no journal, no checkpoint, no evidence.
    `stop` hands the bytes to the engine and wipes the buffer; `wipe` and `close` zero it; the session reports `audio_bytes_held`;
  * this module imports no network code, and the speech engine is a plain callable chosen by settings (none by default). Without an
    engine nothing is transcribed and the person types instead;
  * a transcript becomes a `Draft` marked `needs_review`; `confirm` needs the person's edited text and a human origin. Words that sound
    like approve/apply/merge/delete are flagged but are only text; nothing here (or anywhere) starts, approves or applies from a draft;
  * the project vocabulary (symbols from the context map plus the person's own list) corrects mis-heard technical words, and every
    correction is listed so the interface can highlight it."""
import difflib
import re
import secrets
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from .authority import Action, Origin, authorize

MAX_SECONDS, SAMPLE_RATE, MAX_BYTES = 60, 16_000, 60 * 16_000 * 2  # 16 kHz mono 16-bit, one minute
HIGH_STAKES = re.compile(r"(?i)\b(approve|apply|merge|delete|deploy|push|force|onayla|uygula|birleştir|birlestir|sil|yayınla|yayinla|gönder|gonder|kabul et)\b")
_TR = str.maketrans({"İ": "i", "I": "ı"})
GRANTED, DENIED, UNKNOWN = "granted", "denied", "unknown"


class VoiceError(PermissionError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def fold(text: str) -> str:
    """Case folding that knows Turkish dotted/dotless i, so 'IŞIK' and 'ışık' compare equal."""
    return text.translate(_TR).casefold()


class Session:
    """One push-to-talk recording. States: idle -> armed -> recording -> idle. Everything returns to idle on any failure."""

    def __init__(self, settings: Mapping[str, Any], permission: Callable[[], str], *, clock: Callable[[], float] = time.monotonic):
        self._settings, self._permission, self._clock = settings, permission, clock
        self.state, self._buffer, self._started, self._token = "idle", bytearray(), 0.0, None
        self.closed_reason: str | None = None
        self.audio_written_to_disk = 0  # there is no code path that increments this; the test proves it stays 0 end to end

    @property
    def audio_bytes_held(self) -> int:
        return len(self._buffer)

    def _close(self, reason: str) -> None:
        self._buffer[:] = bytes(len(self._buffer))  # zero before releasing
        self._buffer.clear()
        self.state, self._token, self.closed_reason = "idle", None, reason

    def arm(self) -> str:
        """The person pressed talk. Returns the token the capture side must present with each chunk."""
        if not self._settings.get("voice_enabled"):
            raise VoiceError("VOICE_OFF", "voice input is switched off in the settings")
        if self.state != "idle":
            raise VoiceError("BUSY", "a recording is already in progress")
        permission = self._permission()
        if permission != GRANTED:
            raise VoiceError("NO_PERMISSION", f"microphone permission is {permission}; no recording was started")
        self.state, self._token, self._started, self.closed_reason = "armed", secrets.token_hex(8), self._clock(), None
        return self._token

    def start(self, token: str) -> None:
        if self.state != "armed" or token != self._token:
            raise VoiceError("NOT_ARMED", "recording can only start right after talk was pressed")
        self.state = "recording"

    def feed(self, token: str, chunk: bytes) -> None:
        """PCM from the capture side. Revoked permission, a timeout or an oversize buffer closes the session and discards the audio."""
        if self.state != "recording" or token != self._token:
            raise VoiceError("NOT_RECORDING", "audio arrived while the microphone is closed; it was dropped")
        if not self._settings.get("voice_enabled"):  # switched off while recording: the microphone closes now
            self._close("voice_disabled")
            raise VoiceError("VOICE_OFF", "voice input was switched off; the audio was discarded")
        if self._permission() != GRANTED:
            self._close("permission_revoked")
            raise VoiceError("PERMISSION_REVOKED", "microphone permission was revoked; the audio was discarded")
        if self._clock() - self._started > MAX_SECONDS:
            self._close("too_long")
            raise VoiceError("TOO_LONG", f"recordings stop at {MAX_SECONDS} seconds; the audio was discarded")
        if not isinstance(chunk, (bytes, bytearray)) or len(self._buffer) + len(chunk) > MAX_BYTES:
            self._close("too_large")
            raise VoiceError("TOO_LARGE", "the audio exceeds the limit; it was discarded")
        self._buffer.extend(chunk)

    def stop(self, token: str) -> bytes:
        """Release the audio exactly once, to be transcribed; the session keeps nothing."""
        if self.state != "recording" or token != self._token:
            raise VoiceError("NOT_RECORDING", "there is no recording to stop")
        audio = bytes(self._buffer)
        self._close("stopped")
        return audio

    def wipe(self) -> None:
        """Instant off switch (also used when the app closes or crashes into shutdown)."""
        self._close("wiped")

    def __del__(self) -> None:  # a session that is dropped mid-recording (crash, exception) does not leave audio behind
        try:
            self._buffer[:] = bytes(len(self._buffer))
            self._buffer.clear()
        except Exception:
            pass


def transcribe(engine: Callable[[bytes, str, Sequence[str]], str] | None, audio: bytes, language: str, vocabulary: Sequence[str]) -> str:
    """Run the configured offline engine. No engine = no transcript (typed entry is the fallback)."""
    if engine is None:
        raise VoiceError("NO_ENGINE", "no offline speech engine is configured; type the task instead")
    if language not in ("tr", "en"):
        raise VoiceError("BAD_LANGUAGE", "language must be tr or en")
    text = engine(audio, language, list(vocabulary))
    if not isinstance(text, str):
        raise VoiceError("BAD_TRANSCRIPT", "the engine did not return text")
    return text.strip()[:4000]


def vocabulary_from(context_map: Mapping[str, Any], extra: Iterable[str] = ()) -> list[str]:
    """Project terms: symbol and file names from the context map plus the person's own list. Short or odd tokens are left out."""
    terms = {s["name"] for f in context_map.get("files", []) for s in f["symbols"] if s["kind"] in ("function", "class")}
    terms |= {re.sub(r"\.\w+$", "", f["path"].rsplit("/", 1)[-1]) for f in context_map.get("files", [])}
    terms |= {t for t in extra if isinstance(t, str)}
    return sorted(t for t in terms if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{2,40}", t))


_INFLECTIONS = ("s", "es", "r", "er", "ed", "d", "ing")


def _edits(a: str, b: str) -> int:
    """Levenshtein distance."""
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (x != y))
    return row[-1]


def _is_inflection(word: str, term: str) -> bool:
    return any(term == word + suffix or word == term + suffix for suffix in _INFLECTIONS)


def correct(text: str, vocabulary: Sequence[str], cutoff: float = 0.78) -> tuple[str, list[dict[str, Any]]]:
    """Fix words that are ONE edit away from a known term and only point out words that are two edits away.

    Applying a guess can silently change a sentence's meaning ("rename" is two edits from "readme", "parse" is an inflection of "parser"), so
    only a single-character slip is replaced (`applied: true`); a two-edit near miss is listed as a suggestion (`applied: false`) for the
    person to accept while reviewing. Every entry is returned for highlighting."""
    folded = {fold(v): v for v in vocabulary}
    changes: list[dict[str, Any]] = []

    def swap(match: re.Match[str]) -> str:
        word = match.group(0)
        key = fold(word)
        if key in folded or len(word) < 4:
            return word  # already a known term (any casing) or too short to judge: left exactly as heard
        for near in difflib.get_close_matches(key, list(folded), n=3, cutoff=cutoff):
            if _is_inflection(key, near):
                continue
            distance = _edits(key, near)
            if distance > 2 or (distance == 2 and len(key) < 6):
                continue
            entry = {"heard": word, "replaced_with": folded[near], "at": match.start(), "applied": distance == 1,
                     "score": round(difflib.SequenceMatcher(None, key, near).ratio(), 3)}
            changes.append(entry)
            return folded[near] if distance == 1 else word
        return word
    return re.sub(r"[\wçğıöşüÇĞİÖŞÜ.-]+", swap, text), changes


def to_draft(transcript: str, vocabulary: Sequence[str] = (), *, language: str = "tr") -> dict[str, Any]:
    """A draft is text plus review flags. It has no fields that could start, approve or apply anything."""
    text, changes = correct(transcript, vocabulary)
    words = max(1, len(re.findall(r"\w+", text)))
    return {"draft_id": "vd-" + secrets.token_hex(6), "language": language, "text": text, "original": transcript, "corrections": changes,
            "confidence": round(1 - min(1, len(changes) / words), 3), "high_stakes_words": sorted({m.group(0).casefold() for m in HIGH_STAKES.finditer(text)}),
            "needs_review": True, "confirmed": False, "source": "voice"}


def confirm(draft: Mapping[str, Any], edited_text: str, *, origin: Origin) -> dict[str, Any]:
    """The person read the draft and sends the text they want. Only a human origin can confirm; the result is plain task text."""
    authorize(origin, Action.PRIVILEGED)
    if not isinstance(edited_text, str) or not edited_text.strip() or len(edited_text) > 4000:
        raise VoiceError("EMPTY_TEXT", "a confirmed task needs 1-4000 characters of text")
    return {**draft, "text": edited_text.strip(), "needs_review": False, "confirmed": True, "edited": edited_text.strip() != draft["text"]}


def require_confirmed(draft: Any) -> str:
    """The gate every consumer of a voice draft passes: unconfirmed voice text is refused, so speech alone never reaches plan/start."""
    if isinstance(draft, Mapping) and draft.get("source") == "voice" and not (draft.get("confirmed") is True and draft.get("needs_review") is False):
        raise VoiceError("UNCONFIRMED_DRAFT", "a voice draft must be read and confirmed by a person first")
    return str(draft["text"] if isinstance(draft, Mapping) else draft)


def probe_engines(run: Callable[[list[str]], str]) -> dict[str, Any]:
    """What offline speech recognition this machine really has. `run(argv)` returns stdout; nothing is installed or downloaded."""
    script = ("Add-Type -AssemblyName System.Speech; [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() | "
              "ForEach-Object { $_.Culture.Name }")
    try:
        cultures = sorted({line.strip() for line in run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script]).splitlines() if line.strip()})
    except Exception as error:  # a missing PowerShell is a finding, not a crash
        return {"windows_speech": {"available": False, "cultures": [], "reason": f"probe failed: {type(error).__name__}"}, "usable_for": []}
    usable = [c.split("-")[0] for c in cultures if c.split("-")[0] in ("tr", "en")]
    return {"windows_speech": {"available": bool(cultures), "cultures": cultures, "reason": "installed recognizers" if cultures else "no recognizer is installed"},
            "usable_for": sorted(set(usable)), "turkish": "tr" in usable}


def command_engine(argv: Any, run: Callable[..., Any]) -> Callable[[bytes, str, Sequence[str]], str] | None:
    """Engine = a local program the person chose (`voice_engine_command`, a JSON list). Audio goes to its stdin, text comes back on stdout.

    Nothing is downloaded or installed by Orchestrator. The program is NOT sandboxed: whether it is offline is the person's choice and
    cannot be verified here (reports say so as `network_isolated: false`). Language and vocabulary are passed as arguments, not audio."""
    if argv in (None, "", []):
        return None
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a and "\x00" not in a for a in argv):
        raise VoiceError("BAD_ENGINE", "voice_engine_command must be a non-empty JSON list of strings")

    def engine(audio: bytes, language: str, vocabulary: Sequence[str]) -> str:
        done = run([*argv, "--language", language, *(["--vocabulary", ",".join(vocabulary[:200])] if vocabulary else [])], input=audio, capture_output=True, timeout=MAX_SECONDS + 30, check=False)
        if done.returncode != 0:
            raise VoiceError("ENGINE_FAILED", f"the speech program exited with code {done.returncode}")
        return done.stdout.decode("utf-8", errors="replace")
    return engine
