"""Live per-tool, per-version capability matrix for the UI (B3-07.03).

One row per agent, one cell per user-facing mode. A cell is `verified` (the CLI's own help shows it, the tool is logged in
and not older than the version we checked against), `unverified` (claimed or documented, not proven here: the reason says
which) or `unsupported` (not offered at all). `enabled` is true only for `verified`, so a button can never be live for a
mode that was not proven on this machine. Each cell carries the tool version and the time it was checked.
"""
from __future__ import annotations

import datetime as dt
import shutil
import time

from . import agent_adapters, agent_discovery

# UI mode -> adapter capability name (None: probed here instead)
_cache = []  # [(monotonic, matrix)] for the real machine view only
MODES = {"terminal": "pty", "chat": "chat", "interactive_input": "send_input", "usage": "usage", "resume": "resume", "model_switch": None}
_MODEL_HELP = {"codex": (["exec", "--help"], "--model"), "claude": (["--help"], "--model"), "cursor": (["--help"], "--model"),
               "opencode": (["run", "--help"], "--model"), "antigravity": (["--help"], "--model")}


def _cell(mode, status, reason, version, checked_at):
    return {"mode": mode, "status": status, "enabled": status == "verified", "reason": reason, "version": version, "checked_at": checked_at}


def _model_switch(agent, state, probe, path, version, checked_at):
    spec = _MODEL_HELP.get(agent)
    if spec is None:
        return _cell("model_switch", "unsupported", "no model flag is claimed for this tool", version, checked_at)
    if path is None or state != "ok":
        return _cell("model_switch", "unverified", "tool not usable here, cannot check its help", version, checked_at)
    code, text = probe([path, *spec[0]])
    if code != 0:
        return _cell("model_switch", "unverified", f"help probe failed: {' '.join(spec[0])}", version, checked_at)
    if spec[1] in text:
        return _cell("model_switch", "verified", f"{spec[1]} is in `{' '.join(spec[0])}`", version, checked_at)
    return _cell("model_switch", "unverified", f"{spec[1]} is passed by the runner but absent from `{' '.join(spec[0])}`", version, checked_at)


def build(*, probe=None, which=None, now=None, use_cache=True):
    real = probe is None and which is None and now is None
    if real and use_cache and _cache and time.monotonic() - _cache[0][0] < 30:
        return _cache[0][1]
    probe, which = probe or agent_discovery.Probe(), which or shutil.which
    checked_at = (now or dt.datetime.now(dt.timezone.utc)).isoformat()
    out = {}
    for agent, spec in agent_adapters.ADAPTERS.items():
        found = agent_discovery.discover(agent, probe=probe, which=which)
        row = agent_adapters.verify(agent, probe, which)
        version, usable_tool = found["version"], found["status"] in ("verified",)
        cells = {}
        for mode, cap in MODES.items():
            if cap is None:
                cells[mode] = _model_switch(agent, "ok" if found["status"] in ("verified", "configured", "installed") else "bad", probe, found["path"], version, checked_at)
                if found["status"] != "verified" and cells[mode]["status"] == "verified":
                    cells[mode] = _cell(mode, "unverified", f"flag present, but the tool is {found['status']}: {found['reason']}", version, checked_at)
                continue
            claimed = row["caps"][cap]
            if claimed["status"] == agent_adapters.GATED:
                cells[mode] = _cell(mode, "unsupported", claimed["evidence"], version, checked_at)
            elif claimed["status"] == "verified" and cap != "auth" and not usable_tool:
                cells[mode] = _cell(mode, "unverified", f"flag present, but the tool is {found['status']}: {found['reason']}", version, checked_at)
            elif claimed["status"] == "verified":
                cells[mode] = _cell(mode, "verified", claimed["evidence"], version, checked_at)
            else:  # "source" (documented only) or "advertised_missing" (claimed, not in the CLI's help)
                why = "documented, not probed: " if claimed["status"] == "source" else "claimed but not found in the CLI: "
                cells[mode] = _cell(mode, "unverified", why + claimed["evidence"], version, checked_at)
        out[agent] = {"agent": agent, "tool_status": found["status"], "tool_reason": found["reason"], "version": version,
                      "version_state": found["version_state"], "checked_at": checked_at, "modes": cells}
    result = {"checked_at": checked_at, "agents": out, "modes": list(MODES)}
    if real:
        _cache[:] = [(time.monotonic(), result)]
    return result


def to_markdown(matrix):
    """Release artifact: the matrix as a table a person can read and a reviewer can diff."""
    head = "| agent | tool | " + " | ".join(matrix["modes"]) + " |"
    lines = [f"# Capability matrix ({matrix['checked_at']})", "", "`V` verified, `?` unverified, `-` unsupported. Only `V` enables a button.", "",
             head, "|" + "---|" * (len(matrix["modes"]) + 2)]
    mark = {"verified": "V", "unverified": "?", "unsupported": "-"}
    for agent, row in matrix["agents"].items():
        lines.append(f"| {agent} | {row['tool_status']} {row['version'] or ''} | " + " | ".join(mark[row["modes"][m]["status"]] for m in matrix["modes"]) + " |")
    lines += ["", "## Reasons", ""]
    for agent, row in matrix["agents"].items():
        for mode, cell in row["modes"].items():
            if cell["status"] != "verified":
                lines.append(f"- {agent}/{mode}: {cell['status']} — {cell['reason']}")
    return "\n".join(lines) + "\n"
