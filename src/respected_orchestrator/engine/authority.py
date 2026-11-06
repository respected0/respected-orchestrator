"""Command authority matrix and approval grants (B3-00.03, ADR-022).

Pure policy, not yet wired into runner/CLI/MCP: existing behaviour is unchanged. The desktop shell
(B3-05.02) will call these before any privileged action. Default is deny.
"""
from dataclasses import dataclass
from enum import Enum


class Origin(Enum):
    HUMAN = "human"        # interactive TTY operator or the native human-presence authority
    RENDERER = "renderer"  # WebView content (untrusted)
    MCP = "mcp"
    WORKER = "worker"
    CHILD = "child"        # any other orchestrated process


class Action(Enum):
    READ = "read"              # status, inspect, evidence view
    TASK = "task"              # start / cancel
    SETTINGS = "settings"
    PRIVILEGED = "privileged"  # approve, apply, privileged MCP keys


_ALLOWED = {
    Origin.HUMAN: set(Action),
    Origin.RENDERER: {Action.READ, Action.TASK, Action.SETTINGS},
    Origin.MCP: {Action.READ, Action.TASK},
    Origin.WORKER: set(),
    Origin.CHILD: set(),
}


def effective_origin(claimed, environ):
    """An orchestrated process can never act as a human, whatever origin it claims."""
    return Origin.CHILD if environ.get("RESPECTED_ORCH_CHILD") == "1" else claimed


def authorize(origin, action):
    if action not in _ALLOWED.get(origin, ()):
        raise PermissionError(f"{origin.value} may not perform {action.value}")


@dataclass(frozen=True)
class Grant:
    scope: str
    run_id: str
    patch_sha256: str
    nonce: str


def check_grant(grant, *, scope, run_id, patch_sha256, used_nonces):
    """Bind an approval to scope + run + patch digest and make it single-use. Mutates used_nonces on success."""
    if (grant.scope, grant.run_id, grant.patch_sha256) != (scope, run_id, patch_sha256):
        raise ValueError("Grant does not match this scope, run and patch")
    if grant.nonce in used_nonces:
        raise ValueError("Grant already used")
    used_nonces.add(grant.nonce)
