"""The one table of engine commands (ADR-032). The local API, `rorch session`, the MCP session tools and the desktop relay lists are all
built from it; a face that is left empty means the command is not offered there, on purpose.

`python -m respected_orchestrator.engine.catalog` rewrites the two generated desktop files (source tree only); a test fails when they drift.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .authority import Action

READ, TASK, SETTINGS, PRIVILEGED = Action.READ, Action.TASK, Action.SETTINGS, Action.PRIVILEGED


@dataclass(frozen=True)
class Entry:
    name: str
    action: Action
    op: str | None = None  # the RPP operation it wraps, when it wraps one
    cli: tuple | None = None  # (`rorch <group>` verb, input): None = JSON object on stdin, "" = no input, a name = one optional plain word
    mcp: tuple | None = None  # (tool name, description, input schema, read-only)
    desktop: str | None = None  # the relay list the renderer may use it through: session | task | voice | attach | read
    group: str = "session"  # the `rorch` command its CLI verb lives under: session | task


def _object(required, **properties):
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


_PROJECT_ID = {"type": "string", "description": "Any name you choose for the project; a session is addressed by (session_id, project_id)"}
_SESSION_ID = {"type": "string", "description": "loc_* id returned by orchestrator_session_start"}
_TEXT = {"type": "string"}
_TURN = _object(["project_id", "session_id"], project_id=_PROJECT_ID, session_id=_SESSION_ID)

ENTRIES = (
    Entry("hello", READ),
    Entry("catalog.list", READ, desktop="read"),
    Entry("engine.manifest", READ, "manifest"),
    Entry("engine.health", READ, "health"),
    Entry("settings.schema", READ, "settings.schema"),
    Entry("settings.readback", READ, "settings.readback"),
    Entry("settings.validate", READ, "settings.validate"),
    Entry("settings.apply", SETTINGS, "settings.apply"),
    Entry("evidence.view", READ, "evidence.view"),
    Entry("memory.status", READ, "memory.status"),
    Entry("events.snapshot", READ),
    Entry("events.since", READ),
    # Live stream (ADR-034): the connection that sends this becomes one-way. No desktop relay list: the shell opens the stream itself.
    # No MCP tool: a tool call cannot receive pushes; MCP clients read `live` from orchestrator_session_events.
    Entry("events.subscribe", READ, cli=("watch", "project_id")),
    Entry("runs.active", READ),
    Entry("runs.list", READ, desktop="read"),
    Entry("projects.list", READ, desktop="read"),
    Entry("plan.view", READ),
    Entry("plan.create", TASK),
    Entry("plan.edit", TASK),
    Entry("plan.start", TASK),
    Entry("project.status", READ, desktop="read"),
    Entry("project.cancel", TASK),
    Entry("project.resume", TASK),
    # One isolated task run: the same records `rorch create/start` and the in-process MCP tools write (KALAN_ISLER 1.1).
    Entry("task.start", TASK, cli=("start", None), group="task", desktop="task"),
    Entry("task.status", READ, cli=("status", "run_id"), group="task", desktop="task"),
    Entry("task.cancel", TASK, cli=("cancel", "run_id"), group="task", desktop="task"),
    Entry("task.retry", TASK, cli=("retry", "run_id"), group="task", desktop="task"),
    Entry("review.view", READ),
    Entry("activity.list", READ, desktop="read"),
    Entry("agents.discover", READ),
    Entry("agent.describe", READ, cli=("describe", "agent"), desktop="session", mcp=(
        "orchestrator_agent_describe", "What an agent CLI on this machine is and can do: readiness, chat and terminal interfaces, capabilities, "
        "permission modes, model selection (ADR-033). Without `agent`: every known agent. Read-only probes only; no agent is started.",
        _object([], agent={"type": "string"}), True)),
    Entry("capabilities.scan", READ),
    Entry("capabilities.inventory", READ),
    Entry("capabilities.recommend", READ, desktop="read"),
    Entry("team.view", READ, desktop="read"),
    Entry("analytics.summary", READ, desktop="read"),
    Entry("voice.status", READ, desktop="read"),
    Entry("voice.start", TASK, desktop="voice"),
    Entry("voice.feed", TASK, desktop="voice"),
    Entry("voice.stop", TASK, desktop="voice"),
    Entry("voice.cancel", TASK, desktop="voice"),
    Entry("attachment.status", READ, desktop="read"),
    Entry("attachment.arm", TASK, desktop="attach"),
    Entry("attachment.part", TASK, desktop="attach"),
    Entry("attachment.stage", TASK, desktop="attach"),
    Entry("attachment.preview", READ, desktop="read"),
    Entry("attachment.describe", READ),
    Entry("attachment.list", READ, desktop="read"),
    Entry("attachment.cancel", TASK, desktop="attach"),
    Entry("attachment.delete", TASK, desktop="attach"),
    Entry("attachment.commit", PRIVILEGED),
    Entry("attachment.share", PRIVILEGED),
    Entry("attachment.revoke", PRIVILEGED),
    Entry("roles.view", READ),
    Entry("roles.plan_edit", READ),
    Entry("artifact.list", READ),
    Entry("artifact.read", READ),
    Entry("approval.open", TASK),
    Entry("approval.decide", PRIVILEGED),
    Entry("approval.apply", PRIVILEGED),
    Entry("sessions.list", READ, cli=("list", "project_id"), desktop="session", mcp=(
        "orchestrator_session_list", "List the engine's live chat sessions and saved conversations for a project_id. Read-only.",
        _object([], project_id=_PROJECT_ID), True)),
    Entry("session.start", TASK, cli=("start", None), desktop="session", mcp=(
        "orchestrator_session_start", "Start a chat session with a coding agent in a project folder and send its first message (the turn runs in the "
        "background; read it with orchestrator_session_events). Only agents with a verified chat adapter work.",
        _object(["project_id", "project_root", "text"], project_id=_PROJECT_ID, project_root={"type": "string", "description": "existing absolute folder"},
                text=_TEXT, agent={"type": "string"}, model={"type": "string"}, resume_session={"type": "string"},
                continue_conversation={"type": "string"}), False)),
    Entry("session.events", READ, cli=("events", None), desktop="session", mcp=(
        "orchestrator_session_events", "Events and result of the session's latest turn; while a turn runs, `live` holds its events so far. Read-only.",
        _TURN, True)),
    Entry("session.send", TASK, cli=("send", None), desktop="session", mcp=(
        "orchestrator_session_send", "Send the next message to a session.",
        _object(["project_id", "session_id", "text"], project_id=_PROJECT_ID, session_id=_SESSION_ID, text=_TEXT), False)),
    Entry("session.retry", TASK, cli=("retry", None), desktop="session"),
    Entry("session.interrupt", TASK, cli=("interrupt", None), desktop="session", mcp=(
        "orchestrator_session_interrupt", "Interrupt the turn that is running.", _TURN, False)),
    Entry("session.cancel", TASK, cli=("cancel", None), desktop="session", mcp=("orchestrator_session_cancel", "End a session.", _TURN, False)),
    Entry("session.resume", TASK, cli=("resume", None), desktop="session", mcp=(
        "orchestrator_session_resume", "Resume an interrupted session.", _TURN, False)),
    Entry("session.models", READ, cli=("models", "agent"), desktop="session"),
    Entry("session.defaults", READ, cli=("defaults", ""), desktop="session"),
    Entry("session.defaults.set", SETTINGS, desktop="session"),
    Entry("session.transcript", READ, cli=("transcript", None), desktop="session", mcp=(
        "orchestrator_session_transcript", "The session's saved conversation, one page of turns at a time (newest first; `first` of a reply is the "
        "`before` of the page above it). Read-only.",
        _object(["session_id"], session_id=_SESSION_ID, before={"type": "integer", "minimum": 0}, limit={"type": "integer", "minimum": 1, "maximum": 200}), True)),
    Entry("session.forget", TASK, cli=("forget", None), desktop="session"),
)
BY_NAME = {entry.name: entry for entry in ENTRIES}
assert len(BY_NAME) == len(ENTRIES), "a command is listed twice"

CLI = {(entry.group, entry.cli[0]): entry for entry in ENTRIES if entry.cli}  # (`rorch` command, verb) -> entry
MCP = {entry.mcp[0]: entry for entry in ENTRIES if entry.mcp}  # tool name -> entry
DESKTOP_GROUPS = ("session", "task", "voice", "attach", "read")


def desktop(group):
    return [entry.name for entry in ENTRIES if entry.desktop == group]


def listing(allowed):
    """What `catalog.list` answers: the entries `allowed(entry)` accepts, with the faces each one has."""
    return [{"name": e.name, "action": e.action.name.lower(), "cli": f"{e.group} {e.cli[0]}" if e.cli else None, "mcp": e.mcp[0] if e.mcp else None,
             "desktop": e.desktop} for e in ENTRIES if allowed(e)]


_NOTE = "Generated from src/respected_orchestrator/engine/catalog.py by `python -m respected_orchestrator.engine.catalog`. Do not edit."


def render_ts():
    def array(names):
        return "[" + ", ".join(f"'{name}'" for name in names) + "] as const"
    return (f"// {_NOTE}\nexport const COMMANDS = {array(BY_NAME)};\n"
            + "".join(f"export const {group.upper()}_COMMANDS = {array(desktop(group))};\n" for group in DESKTOP_GROUPS))


def render_rs():
    def array(group):
        names = desktop(group)
        return f"pub const {group.upper()}_COMMANDS: [&str; {len(names)}] = [" + ", ".join(f'"{name}"' for name in names) + "];\n"
    return f"// {_NOTE}\n" + "".join(array(group) for group in DESKTOP_GROUPS)


def generated(root):
    """path -> text of the desktop files that mirror this table."""
    desktop_dir = Path(root) / "desktop"
    return {desktop_dir / "src" / "contracts" / "catalog.ts": render_ts(), desktop_dir / "src-tauri" / "src" / "catalog.rs": render_rs()}


if __name__ == "__main__":
    for path, text in generated(Path(__file__).resolve().parents[3]).items():
        path.write_bytes(text.encode("utf-8"))
        print(path)
