"""Reference offline speech engine for `voice_engine_command` (B4-06). Not part of the installed program.

Protocol (engine/voice.py `command_engine`): raw 16 kHz mono 16-bit little-endian PCM on stdin; `--language tr|en` and an optional
`--vocabulary a,b,c` on the command line; the transcript on stdout. It runs only from files already on disk: no model is fetched,
Hugging Face is told to stay offline, and any attempt to open a socket raises, so a mistake here cannot send audio anywhere.

    <venv>\\Scripts\\python.exe -I packaging\\voice\\faster_whisper_stt.py --language en < audio.pcm

Model directory: `--model DIR`, else the environment variable RESPECTED_STT_MODEL, else `<venv>/../models/faster-whisper-small`.
"""
import argparse
import os
import socket
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


def _no_network(*args, **kwargs):
    raise RuntimeError("the speech engine is offline by design: a socket was requested")


def cut_the_network() -> None:
    """Applied after the heavy imports (asyncio/ssl subclass `socket` while importing): from here on nothing can open a connection."""
    socket.socket = _no_network  # type: ignore[assignment,misc]
    socket.create_connection = _no_network  # type: ignore[assignment]
    socket.getaddrinfo = _no_network  # type: ignore[assignment]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=["tr", "en"], required=True)
    parser.add_argument("--vocabulary", default="")
    parser.add_argument("--model", default=os.environ.get("RESPECTED_STT_MODEL") or str(Path(sys.prefix).resolve().parent / "models" / "faster-whisper-small"))
    args = parser.parse_args()
    import numpy as np
    from faster_whisper import WhisperModel

    cut_the_network()
    raw = sys.stdin.buffer.read()
    if not raw or len(raw) % 2:
        print("no audio or a half sample", file=sys.stderr)
        return 2
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    model = WhisperModel(args.model, device="cpu", compute_type="int8", local_files_only=True)
    terms = [t.strip() for t in args.vocabulary.split(",") if t.strip()][:100]
    prompt = ("Teknik terimler: " if args.language == "tr" else "Technical terms: ") + ", ".join(terms) if terms else None
    segments, _info = model.transcribe(audio, language=args.language, beam_size=1, initial_prompt=prompt, vad_filter=True, condition_on_previous_text=False)
    sys.stdout.write(" ".join(s.text.strip() for s in segments).strip() + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
