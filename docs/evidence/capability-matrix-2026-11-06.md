# Capability matrix (2026-11-06T21:05:07.302862+00:00)

`V` verified, `?` unverified, `-` unsupported. Only `V` enables a button.

| agent | tool | terminal | chat | interactive_input | usage | resume | model_switch |
|---|---|---|---|---|---|---|---|
| codex | verified codex-cli 0.160.1 | - | V | ? | ? | V | V |
| claude | verified 2.1.318 (Claude Code) | - | V | V | ? | V | V |
| cursor | verified 2026.10.22-27dcf5f | - | V | ? | ? | V | V |
| opencode | configured opencode v2.2.3 | - | ? | ? | ? | ? | ? |
| antigravity | installed 1.5.0 | - | - | - | - | - | ? |
| custom | configured  | - | - | - | - | - | - |

## Reasons

- codex/terminal: unsupported — PTY awaits the ConPTY+AppContainer gate (B3-03.02)
- codex/interactive_input: unverified — documented, not probed: app-server/queue exist but no probed non-interactive stdin protocol
- codex/usage: unverified — documented, not probed: token counts not probed in the JSONL stream
- claude/terminal: unsupported — PTY awaits the ConPTY+AppContainer gate (B3-03.02)
- claude/usage: unverified — documented, not probed: result message usage fields not probed
- cursor/terminal: unsupported — PTY awaits the ConPTY+AppContainer gate (B3-03.02)
- cursor/interactive_input: unverified — documented, not probed: no probed streaming input
- cursor/usage: unverified — documented, not probed: not probed
- opencode/terminal: unsupported — PTY awaits the ConPTY+AppContainer gate (B3-03.02)
- opencode/chat: unverified — flag present, but the tool is configured: stored credentials found; their validity cannot be checked without a model call
- opencode/interactive_input: unverified — documented, not probed: acp server exists; not probed
- opencode/usage: unverified — documented, not probed: not probed
- opencode/resume: unverified — flag present, but the tool is configured: stored credentials found; their validity cannot be checked without a model call
- opencode/model_switch: unverified — flag present, but the tool is configured: stored credentials found; their validity cannot be checked without a model call
- antigravity/terminal: unsupported — PTY awaits the ConPTY+AppContainer gate (B3-03.02)
- antigravity/chat: unsupported — no adapter contract for this capability yet
- antigravity/interactive_input: unsupported — no adapter contract for this capability yet
- antigravity/usage: unsupported — no adapter contract for this capability yet
- antigravity/resume: unsupported — no adapter contract for this capability yet
- antigravity/model_switch: unverified — flag present, but the tool is installed: auth_unknown: login state could not be read
- custom/terminal: unsupported — PTY awaits the ConPTY+AppContainer gate (B3-03.02)
- custom/chat: unsupported — no adapter contract for user-defined commands
- custom/interactive_input: unsupported — no adapter contract for user-defined commands
- custom/usage: unsupported — no adapter contract for user-defined commands
- custom/resume: unsupported — no adapter contract for user-defined commands
- custom/model_switch: unsupported — no model flag is claimed for this tool
