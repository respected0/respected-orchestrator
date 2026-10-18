# Codex reconnect notice review

**Verdict:** approve with one tightened implementation.

The production symptom was a valid Codex JSONL stream that contained a top-level
`error` event for a non-fatal reconnect, followed by a final agent message and
`turn.completed`. The original parser treated every top-level `error` event as
fatal, so a completed worker result was classified as `worker_failed`.

The reviewed fix is directionally correct: reconnect notices are tolerated only
when they are top-level `error` events, the message is a string beginning with
the exact production prefix `Reconnecting...`, the stream contains no
`turn.failed`, contains no other top-level error, and ends in
`turn.completed`. This review adds a requirement that the stream contain
exactly one `turn.completed`, preventing concatenated or multi-turn stdout from
being accepted as a single worker result.

An error after the final `turn.completed` is rejected because the stream no
longer ends in completion. A reconnect notice between the final agent message
and `turn.completed` remains acceptable because completion is the stream's
authoritative terminal state. Reconnect text inside an agent message is not
special-cased and cannot itself bypass final-JSON validation.

## Residual risks

- The exact prefix is intentionally case- and whitespace-sensitive; a future
  Codex wording change will fail closed until evidence supports the new shape.
- A one-turn stream can still contain multiple agent messages; the parser
  intentionally uses the last one as the final result, as before.
- Acceptance tests were not run in this sandbox because Python execution is
  prohibited by the task environment.
