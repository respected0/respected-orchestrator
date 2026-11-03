"""Fail-closed stdio client for OpenCode's Agent Client Protocol (ACP).

OpenCode's ACP mode is interactive: JSON-RPC requests and responses share the worker's
stdin/stdout.  The engine therefore starts the stdout/stderr readers before the
``on_ready`` callback runs this client.  Prompts travel only in ``session/prompt`` and
never in argv.
"""
from __future__ import annotations

import json
from pathlib import Path
import queue
import re
import time


PROTOCOL_VERSION = 1
_SUCCESS = {"success", "complete", "completed", "ok"}
_VALID_STATUS = _SUCCESS | {"failed"}
_EOF = object()


class AcpError(Exception):
    """A bounded ACP failure with the provider status the engine must record."""

    def __init__(self, message: str, *, kind: str = "worker_failed"):
        super().__init__(message[:1000])
        self.kind = kind

    @property
    def provider_status(self) -> str:
        return {"auth": "AUTH_REQUIRED", "limit": "LIMIT_EXHAUSTED", "timed_out": "TIMEOUT"}.get(
            self.kind, "WORKER_FAILED"
        )


class LineQueue:
    """Thread-safe bridge from ``processes.execute`` output readers to the ACP client."""

    def __init__(self):
        self._items: queue.Queue = queue.Queue()

    def push(self, name: str, line: str) -> None:
        self._items.put((name, line))

    def close(self, name: str) -> None:
        self._items.put((name, _EOF))

    def get(self, timeout: float):
        return self._items.get(timeout=timeout)


def _kind_for_message(message: str) -> str:
    value = message.casefold()
    if any(marker in value for marker in ("authentication required", "unauthenticated", "login required", "auth required")):
        return "auth"
    if any(marker in value for marker in ("usage limit", "limit reached", "limit exhausted", "quota", "rate limit")):
        return "limit"
    return "worker_failed"


def _failure_payload(error: str) -> dict:
    return {"status": "failed", "error": error[:300]}


def _json_object(value: str) -> dict | None:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _final_object(text: str) -> dict | None:
    """Accept a bare object or exactly one fenced object, never JSON from free prose."""
    payload = _json_object(text)
    if payload is not None:
        return payload
    if text.count("```") != 2:
        return None
    match = re.search(r"```[ \t]*(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", text,
                      re.DOTALL | re.IGNORECASE)
    return _json_object(match.group(1)) if match else None


class Session:
    def __init__(self, stdin, lines: LineQueue, *, deadline: float, cancel_path: Path | None = None):
        self.stdin = stdin
        self.lines = lines
        self.deadline = deadline
        self.cancel_path = cancel_path
        self._ident = 0
        self._messages: list[tuple[str, str]] = []

    def _send(self, message: dict) -> None:
        try:
            self.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
            self.stdin.flush()
        except (OSError, ValueError) as error:
            raise AcpError(f"ACP stdin closed: {error}", kind="worker_failed") from error

    def _next_message(self) -> dict:
        while True:
            if self.cancel_path is not None and self.cancel_path.exists():
                raise AcpError("ACP session cancelled", kind="cancelled")
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise AcpError("ACP session timed out", kind="timed_out")
            try:
                name, line = self.lines.get(timeout=min(0.1, remaining))
            except queue.Empty:
                continue
            if line is _EOF:
                if name == "stdout":
                    raise AcpError("OpenCode ACP closed stdout before a response", kind="worker_failed")
                continue
            if name != "stdout":
                continue
            try:
                message = json.loads(line)
            except (TypeError, json.JSONDecodeError) as error:
                raise AcpError("OpenCode ACP emitted malformed JSON", kind="worker_failed") from error
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                raise AcpError("OpenCode ACP emitted an invalid JSON-RPC message", kind="worker_failed")
            return message

    def _server_request(self, message: dict) -> None:
        method, ident = message.get("method"), message.get("id")
        if ident is None:
            return
        if method == "session/request_permission":
            # An unattended engine never infers consent from an ACP prompt.  The documented
            # cancellation outcome rejects this request and leaves the task to fail closed.
            self._send({"jsonrpc": "2.0", "id": ident, "result": {"outcome": {"outcome": "cancelled"}}})
            return
        # fs/*, terminal/* and every unknown client method stay unavailable.  The engine
        # grants only the worker's own file tools; ACP client capabilities are never widenings.
        self._send({"jsonrpc": "2.0", "id": ident,
                    "error": {"code": -32601, "message": "ACP client method is not available"}})

    def _record(self, message: dict) -> None:
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if message.get("method") != "session/update":
            return
        update = params.get("update") if isinstance(params.get("update"), dict) else {}
        if update.get("sessionUpdate") != "agent_message_chunk":
            return
        content = update.get("content") if isinstance(update.get("content"), dict) else {}
        text = content.get("text")
        if content.get("type") != "text" or not isinstance(text, str):
            raise AcpError("OpenCode ACP emitted a malformed assistant message", kind="worker_failed")
        message_id = update.get("messageId")
        key = message_id if isinstance(message_id, str) and message_id else "__default__"
        if self._messages and self._messages[-1][0] == key:
            self._messages[-1] = (key, self._messages[-1][1] + text)
        else:
            self._messages.append((key, text))

    def _receive_response(self, expected: int) -> dict:
        while True:
            message = self._next_message()
            if "method" in message:
                self._server_request(message)
                self._record(message)
                continue
            if message.get("id") != expected:
                raise AcpError("OpenCode ACP replied with an unexpected request id", kind="worker_failed")
            error = message.get("error")
            if error is not None:
                if isinstance(error, dict):
                    message_text = str(error.get("message") or error.get("data") or "ACP request failed")
                else:
                    message_text = str(error)
                raise AcpError(message_text, kind=_kind_for_message(message_text))
            result = message.get("result")
            if not isinstance(result, dict):
                raise AcpError("OpenCode ACP returned a non-object result", kind="worker_failed")
            return result

    def request(self, method: str, params: dict) -> dict:
        self._ident += 1
        self._send({"jsonrpc": "2.0", "id": self._ident, "method": method, "params": params})
        return self._receive_response(self._ident)

    def final_text(self) -> str:
        return self._messages[-1][1] if self._messages else ""

    def initialize(self) -> dict:
        result = self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "clientCapabilities": {},
            "clientInfo": {"name": "Respected Orchestrator", "version": "1"},
        })
        if result.get("protocolVersion") != PROTOCOL_VERSION:
            raise AcpError("OpenCode ACP protocol version is incompatible", kind="worker_failed")
        return result

    def new_session(self, cwd: Path) -> dict:
        result = self.request("session/new", {"cwd": str(cwd), "mcpServers": []})
        if not isinstance(result.get("sessionId"), str) or not result["sessionId"]:
            raise AcpError("OpenCode ACP did not return a session id", kind="worker_failed")
        return result

    def set_option(self, session_id: str, config_id: str, value: str, options: list) -> str:
        option = next((item for item in options if isinstance(item, dict) and item.get("id") == config_id), None)
        if option is None:
            raise AcpError(f"OpenCode ACP does not expose {config_id} selection", kind="worker_failed")
        values = {item.get("value") for item in option.get("options", []) if isinstance(item, dict)}
        if values and value not in values:
            raise AcpError(f"OpenCode model or mode is unavailable: {value}", kind="worker_failed")
        result = self.request("session/set_config_option", {
            "sessionId": session_id, "configId": config_id, "value": value,
        })
        selected = next((item for item in result.get("configOptions", [])
                         if isinstance(item, dict) and item.get("id") == config_id), None)
        if isinstance(selected, dict) and selected.get("currentValue") not in (None, value):
            raise AcpError(f"OpenCode did not apply {config_id}={value}", kind="worker_failed")
        return value

    def prompt(self, session_id: str, text: str) -> dict:
        result = self.request("session/prompt", {
            "sessionId": session_id,
            "prompt": [{"type": "text", "text": text}],
        })
        if result.get("stopReason") != "end_turn":
            raise AcpError("OpenCode ACP did not finish its turn", kind="worker_failed")
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        return {"usage": usage, "stop_reason": "end_turn"}


def run_session(stdin, lines: LineQueue, *, cwd: Path, prompt: str, model: str | None,
                write: bool, deadline: float, cancel_path: Path | None = None) -> dict:
    session = Session(stdin, lines, deadline=deadline, cancel_path=cancel_path)
    session.initialize()
    created = session.new_session(cwd)
    session_id = created["sessionId"]
    options = created.get("configOptions") if isinstance(created.get("configOptions"), list) else []
    selected_model = None
    if model:
        selected_model = session.set_option(session_id, "model", model, options)
    session.set_option(session_id, "mode", "build" if write else "plan", options)
    turn = session.prompt(session_id, prompt)
    text = session.final_text()
    payload = _final_object(text)
    if payload is None:
        payload = _failure_payload("OpenCode final assistant message is not a JSON object")
    elif not isinstance(payload.get("status"), str) or payload["status"].casefold() not in _VALID_STATUS:
        payload = _failure_payload("OpenCode final result has no valid status")
    elif payload.get("error"):
        payload = dict(payload)
    return {"payload": payload, "usage": turn["usage"], "model": selected_model, "stop_reason": turn["stop_reason"]}
