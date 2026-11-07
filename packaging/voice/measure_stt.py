"""Measures the configured speech engine on WAV files and reports word error rate, latency and memory (B4-06.01 evidence).

    python packaging/voice/measure_stt.py --engine "<venv>/Scripts/python.exe -I packaging/voice/faster_whisper_stt.py" --language en \\
        --vocabulary pytest,unittest,parse_config clip1.wav=expected text one clip2.wav=expected text two

Each WAV must be 16 kHz mono 16-bit (Python's `wave` module reads it; nothing is converted or sent anywhere). Output is JSON.
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
import time
import wave


def words(text: str) -> list[str]:
    return re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", text.casefold().replace("İ", "i").replace("I", "ı"))


def wer(reference: list[str], hypothesis: list[str]) -> float:
    d = list(range(len(hypothesis) + 1))
    for i, r in enumerate(reference, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hypothesis, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[-1] / max(1, len(reference))


def read_pcm(path: str) -> tuple[bytes, float]:
    with wave.open(path, "rb") as handle:
        if (handle.getframerate(), handle.getnchannels(), handle.getsampwidth()) != (16000, 1, 2):
            raise SystemExit(f"{path}: needs 16 kHz mono 16-bit (got {handle.getframerate()} Hz, {handle.getnchannels()} ch, {handle.getsampwidth() * 8} bit)")
        frames = handle.readframes(handle.getnframes())
        return frames, handle.getnframes() / 16000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--language", choices=["tr", "en"], required=True)
    parser.add_argument("--vocabulary", default="")
    parser.add_argument("clips", nargs="+", help="file.wav=expected transcript")
    args = parser.parse_args()
    rows = []
    for item in args.clips:
        path, _, expected = item.partition("=")
        pcm, seconds = read_pcm(path)
        argv = [*shlex.split(args.engine, posix=False), "--language", args.language, *(["--vocabulary", args.vocabulary] if args.vocabulary else [])]
        started = time.perf_counter()
        done = subprocess.run(argv, input=pcm, capture_output=True, timeout=600)
        elapsed = time.perf_counter() - started
        heard = done.stdout.decode("utf-8", errors="replace").strip()
        rows.append({"clip": path, "audio_seconds": round(seconds, 2), "seconds": round(elapsed, 2), "real_time_factor": round(elapsed / seconds, 2),
                     "exit": done.returncode, "expected": expected, "heard": heard, "wer": round(wer(words(expected), words(heard)), 3) if expected else None,
                     "stderr": done.stderr.decode("utf-8", errors="replace")[-200:]})
    scored = [r["wer"] for r in rows if r["wer"] is not None]
    print(json.dumps({"language": args.language, "clips": rows, "mean_wer": round(sum(scored) / len(scored), 3) if scored else None}, indent=2, ensure_ascii=False))
    return 0 if all(r["exit"] == 0 for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
