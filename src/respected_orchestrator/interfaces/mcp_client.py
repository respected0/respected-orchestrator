"""EXT-02: a minimal, fail-closed MCP stdio client (JSON-RPC 2.0, newline framed).

A tool result is data. This module never executes tool text; it only returns the parsed response to the caller.
"""
import json
import os
import queue
import subprocess
import threading
import time

from ..engine import winproc

MAX_BYTES = 1_000_000


class McpError(RuntimeError):
    """A transport or protocol failure; callers must fail closed."""


class StdioMcpClient:
    def __init__(self, command, args=(), *, env=None, cwd=None, timeout=20.0, max_bytes=MAX_BYTES):
        if not isinstance(command, str) or not command or not all(isinstance(arg, str) for arg in args):
            raise McpError("MCP_COMMAND_INVALID")
        if not isinstance(timeout, (int, float)) or timeout <= 0 or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise McpError("MCP_LIMIT_INVALID")
        self.timeout = float(timeout)
        self.max_bytes = max_bytes
        self._next_id = 0
        self._bytes = 0
        self._lines = queue.Queue()
        try:
            self._proc = winproc.popen(
                [command, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=cwd, env={**os.environ, **(env or {})}, text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as error:
            raise McpError(f"MCP_START_FAILED: {type(error).__name__}") from None
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            for line in self._proc.stdout:
                self._lines.put(line)
        finally:
            self._lines.put(None)

    def _send(self, message):
        if self._proc.poll() is not None:
            raise McpError("MCP_EXITED")
        try:
            self._proc.stdin.write(json.dumps(message, ensure_ascii=True) + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError) as error:
            raise McpError(f"MCP_WRITE_FAILED: {type(error).__name__}") from None

    def _read(self):
        try:
            line = self._lines.get(timeout=self.timeout)
        except queue.Empty:
            raise McpError("MCP_TIMEOUT") from None
        if line is None:
            raise McpError("MCP_EXITED")
        self._bytes += len(line.encode("utf-8", "replace"))
        if self._bytes > self.max_bytes or len(line) > self.max_bytes:
            raise McpError("MCP_OUTPUT_TOO_LARGE")
        try:
            message = json.loads(line)
        except ValueError:
            raise McpError("MCP_PROTOCOL_INVALID") from None
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise McpError("MCP_PROTOCOL_INVALID")
        return message

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})})

    def request(self, method, params=None):
        self._next_id += 1
        identity = self._next_id
        self._send({"jsonrpc": "2.0", "id": identity, "method": method, **({"params": params} if params is not None else {})})
        while True:
            message = self._read()
            if message.get("id") != identity:
                continue  # notifications and unrelated replies cannot satisfy this call
            if "error" in message:
                error = message.get("error")
                detail = error.get("message") if isinstance(error, dict) else error
                raise McpError(f"MCP_ERROR: {str(detail)[:300]}")
            return message.get("result")

    def initialize(self):
        result = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                             "clientInfo": {"name": "respected-orchestrator", "version": "1"}})
        self.notify("notifications/initialized")
        return result

    def list_tools(self):
        result = self.request("tools/list")
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            raise McpError("MCP_PROTOCOL_INVALID")
        return tools

    def call_tool(self, name, arguments=None):
        if not isinstance(name, str) or not name:
            raise McpError("MCP_TOOL_INVALID")
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        if not isinstance(result, dict):
            raise McpError("MCP_PROTOCOL_INVALID")
        return result

    def close(self):
        try:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        finally:
            for stream in (self._proc.stdin, self._proc.stdout, self._proc.stderr):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
