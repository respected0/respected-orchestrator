"""Agent adapter capability matrix (B3-03.01): what each agent CLI can do, separated into source claim and live proof.

Only read-only probes run (`--version`, `--help`, auth status). A capability is `verified` only when its flag appears in the
installed CLI's own help text; a flag that vanished is `advertised_missing`, never silently `verified`. PTY is not offered
anywhere until the ConPTY+AppContainer gate (B3-03.02) decides; nothing here ever starts an unsandboxed process.
"""
from __future__ import annotations

import re
import shutil
import subprocess

CAPABILITIES = ("chat", "pty", "send_input", "interrupt", "resume", "usage", "auth", "approval")
GATED = "unsupported"  # explicit, not "unknown"

# cap -> (help argv after the binary, token that must appear in that help text) or None (no CLI surface claimed)
# `note` says where the claim comes from; every claim not backed by a help token stays "source" (documented, not probed).
ADAPTERS = {
    "codex": {
        "binaries": ["codex"], "verified_version": (0, 160, 1),
        "caps": {
            "chat": (["exec", "--help"], "--json", "exec --json: events as JSONL on stdout"),
            "resume": (["exec", "--help"], "resume", "exec resume <id>|--last"),
            "approval": (["--help"], "--ask-for-approval", "-a/--ask-for-approval and -s/--sandbox policies"),
            "send_input": (None, None, "app-server/queue exist but no probed non-interactive stdin protocol"),
            "interrupt": (None, None, "process termination only; no probed interrupt message"),
            "usage": (None, None, "token counts not probed in the JSONL stream"),
        },
        "auth": (["login", "status"], r"logged in"),
    },
    "claude": {
        "binaries": ["claude"], "verified_version": (2, 1, 318),
        "caps": {
            "chat": (["--help"], "stream-json", "-p --output-format stream-json"),
            "send_input": (["--help"], "--input-format", "--input-format stream-json (realtime input)"),
            "resume": (["--help"], "--resume", "--resume <id>, --continue"),
            "approval": (["--help"], "--permission-prompts", "--permission-prompts host / --permission-mode"),
            "interrupt": (None, None, "process termination only; no probed interrupt message"),
            "usage": (None, None, "result message usage fields not probed"),
        },
        "auth": (["auth", "status"], r'"loggedIn":\s*true'),
    },
    "cursor": {
        "binaries": ["cursor-agent", "agent"], "verified_version": None,  # date-style versions: compared as text, see below
        "caps": {
            "chat": (["--help"], "stream-json", "-p --output-format stream-json"),
            "resume": (["--help"], "--resume", "--resume <chatId>, --continue"),
            "approval": (["--help"], "--sandbox", "--sandbox <mode>, auto-runs safe tools and prompts for the rest"),
            "send_input": (None, None, "no probed streaming input"),
            "interrupt": (None, None, "process termination only"),
            "usage": (None, None, "not probed"),
        },
        "auth": (["status"], r"logged in"),
    },
    "opencode": {
        "binaries": ["opencode"], "verified_version": (2, 2, 3),
        "caps": {
            "chat": (["run", "--help"], "--format", "run --format json"),
            "resume": (["run", "--help"], "--session", "run --session <id>, --continue"),
            "approval": (["run", "--help"], "--auto", "--auto auto-approves non-denied permissions"),
            "send_input": (None, None, "acp server exists; not probed"),
            "interrupt": (None, None, "process termination only"),
            "usage": (None, None, "not probed"),
        },
        # stored credentials are not proof they are valid, so a hit only means "configured"
        "auth": (["auth", "list"], r"stored"),
    },
    "antigravity": {"binaries": ["antigravity"], "verified_version": None, "caps": {}, "auth": None},
    "custom": {"binaries": [], "verified_version": None, "caps": {}, "auth": None},  # nothing is assumed about user commands
}


def _run(argv, timeout=30):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                              stdin=subprocess.DEVNULL, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    return done.returncode, done.stdout + done.stderr


def _parse(text):
    found = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in found.groups()) if found else None


def verify(agent, run=_run, which=shutil.which):
    """Probe one agent and return the matrix row: per capability status and evidence, plus presence/version/auth."""
    spec = ADAPTERS[agent]
    path = next((p for p in (which(b) for b in spec["binaries"]) if p), None)
    row = {"agent": agent, "found": path is not None, "version": None, "version_state": "unknown", "auth": "unknown", "caps": {}}
    unsupported = "binary not found" if spec["binaries"] else "no adapter contract for user-defined commands"
    for cap in CAPABILITIES:
        row["caps"][cap] = {"status": GATED, "evidence": "PTY awaits the ConPTY+AppContainer gate (B3-03.02)" if cap == "pty" else unsupported}
    if path is None:
        return row
    code, text = run([path, "--version"])
    row["version"] = text.strip().splitlines()[0] if code == 0 and text.strip() else None
    floor, seen = spec["verified_version"], _parse(row["version"])
    if floor and seen:
        row["version_state"] = "ok" if seen >= floor else "older_than_verified"
    elif seen or row["version"]:
        row["version_state"] = "unpinned"  # date-style versions have no floor yet
    helps = {}
    for cap, (argv, token, note) in spec["caps"].items():
        if argv is None:
            row["caps"][cap] = {"status": "source", "evidence": note}
            continue
        key = tuple(argv)
        if key not in helps:
            helps[key] = run([path, *argv])
        rc, out = helps[key]
        if rc is None or rc != 0:
            row["caps"][cap] = {"status": "advertised_missing", "evidence": f"help probe failed: {' '.join(argv)}"}
        elif token in out:
            status = "verified" if row["version_state"] != "older_than_verified" else "source"
            row["caps"][cap] = {"status": status, "evidence": note}
        else:
            row["caps"][cap] = {"status": "advertised_missing", "evidence": f"{token!r} not in {' '.join(argv)}"}
    if spec["auth"]:
        argv, ok = spec["auth"]
        rc, out = run([path, *argv])
        row["auth"] = "unknown" if rc is None else ("ok" if rc == 0 and re.search(ok, out, re.I) else "needs_login")
        row["caps"]["auth"] = {"status": "verified", "evidence": f"{' '.join(argv)} (read-only)"}
    return row


def matrix(run=_run, which=shutil.which):
    return {agent: verify(agent, run, which) for agent in ADAPTERS}


def usable(row, cap):
    """A mode may be started only when verified AND the agent is present and logged in; everything else is closed."""
    return row["found"] and row["auth"] == "ok" and row["caps"][cap]["status"] == "verified"
