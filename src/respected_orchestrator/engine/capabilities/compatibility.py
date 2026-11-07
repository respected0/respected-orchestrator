"""CompatibilityResolver (B4-03.01): can this discovered capability work with this agent, for this project? Pure and offline.

Input is a record from `normalize.build` (nothing is run, contacted or read again). Output is `compatible`, `incompatible` or
`unknown`, never a bare yes/no, and every reason says which of the three it supports. Compatibility is a different question from
trust: this module never reads or changes `status.trusted`, and a compatible capability is not an approved one.

What is known comes only from this repository: which clients have a config location for MCP servers or skills (`paths.matrix`) and
that a `stdio` MCP server is a command the client spawns. Other transports (http, sse, ...) and anything that would need a program
to be run to find out (package runners, versions) are `unknown`, not guessed."""
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import paths

CONFIRMED_TRANSPORTS = {"stdio"}
_PROBE_HOME = Path("/probe-home")


def clients() -> dict[str, set[str]]:
    """{client: kinds it has a config location for}, taken from the discovery matrix so the two cannot drift apart."""
    out: dict[str, set[str]] = {}
    for row in paths.matrix(_PROBE_HOME, _PROBE_HOME / "project"):
        if row["client"] != "shared":  # a shared skills folder is not an agent
            out.setdefault(row["client"], set()).add(row["kind"])
    return out


def _why(verdict: str, code: str, detail: str) -> dict[str, str]:
    return {"verdict": verdict, "code": code, "detail": detail}


def resolve(record: Mapping[str, Any], target_client: str, *, project: str | None = None) -> dict[str, Any]:
    """{verdict, reasons[{verdict, code, detail}], capability, target_client}. `project` is the task's project root, if any."""
    reasons: list[dict[str, str]] = []
    known = clients()
    kind, entry, status = record.get("kind"), record.get("entry") or {}, record.get("status") or {}
    if target_client not in known:
        reasons.append(_why("incompatible", "client_unsupported", f"{target_client!r} has no config location in the discovery matrix"))
    elif kind not in known[target_client]:
        reasons.append(_why("incompatible", "kind_unsupported", f"{target_client} has no known place for {kind} capabilities"))
    if kind == "skill":
        if not entry.get("has_skill_md"):
            reasons.append(_why("incompatible", "skill_file_missing", "the folder has no SKILL.md"))
    elif kind == "mcp":
        transport = entry.get("transport")
        if transport == "unknown":
            reasons.append(_why("incompatible", "no_command_or_url", "the entry declares neither a command nor a URL"))
        elif transport not in CONFIRMED_TRANSPORTS:
            reasons.append(_why("unknown", "transport_unconfirmed", f"transport {transport!r} is not confirmed for {target_client}"))
        installed = (status.get("installed") or {}).get("state")
        if installed is False:
            reasons.append(_why("incompatible", "missing_binary", (status.get("installed") or {}).get("reason", "program not found")))
        elif installed is None and transport == "stdio":
            reasons.append(_why("unknown", "binary_unverifiable", (status.get("installed") or {}).get("reason", "cannot be told without running it")))
    else:
        reasons.append(_why("incompatible", "kind_unsupported", f"unknown capability kind {kind!r}"))
    if record.get("scope") == "project":
        mine = record.get("project_path")
        if project is None:
            reasons.append(_why("unknown", "project_not_given", "a project-scoped capability needs the task's project to be judged"))
        elif mine and Path(mine).resolve() != Path(project).resolve():
            reasons.append(_why("incompatible", "wrong_project", "it is scoped to a different project"))
    for warning in record.get("warnings", []):
        if warning.get("kind") == "duplicate_name" and not warning.get("same_definition", True):
            reasons.append(_why("unknown", "ambiguous_duplicate", "another definition with the same name differs, so which one is meant is unclear"))
    verdict = "incompatible" if any(r["verdict"] == "incompatible" for r in reasons) else "unknown" if reasons else "compatible"
    if not reasons:
        reasons.append(_why("compatible", "all_checks_passed", "kind, transport, program and scope are consistent with the target"))
    return {"capability": record.get("id"), "target_client": target_client, "verdict": verdict, "reasons": reasons}


def resolve_all(inventory: Mapping[str, Any], target_client: str, *, project: str | None = None) -> dict[str, Any]:
    """Every record of a `normalize.build` result, plus counts per verdict."""
    rows = [resolve(rec, target_client, project=project) for rec in inventory.get("capabilities", [])]
    return {"target_client": target_client, "results": rows,
            "counts": {v: sum(r["verdict"] == v for r in rows) for v in ("compatible", "incompatible", "unknown")}}
