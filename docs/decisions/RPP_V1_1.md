# RPP v1.1 server-side contract (backward-compatible extension of v1.0)

## Status

Proposed additive extension of the Respected Product Protocol (RPP). v1.1 is a strict
superset of v1.0: existing v1.0 request and response shapes and existing op
behaviour are unchanged. This document specifies only the additions; it does not
redesign anything that exists.

## Decision

RPP v1.1 adds lifecycle operations, version negotiation across 1.0..1.1, seven new
typed errors, and a richer `manifest`. The transport is unchanged: one JSON request on
stdin, one JSON response line on stdout, from the private entry point
(`src/respected_orchestrator/interfaces/rpp.py`), reached via
`python -m respected_orchestrator --data-root DATA rpp`. No daemon, no listener. The
new surface is implemented in the same allow-list registry pattern the existing ops
use (`_OPS`, `src/respected_orchestrator/interfaces/rpp.py:255`).

## Version negotiation

- `PROTOCOL_MIN` stays `"1.0"`; `PROTOCOL_MAX` becomes `"1.1"`
  (`src/respected_orchestrator/interfaces/rpp.py:19`).
- A request whose `rpp` is outside `[min, max]` fails with `PROTOCOL_UNSUPPORTED`
  (existing error, unchanged behaviour).
- The response `rpp` echoes the negotiated version, which is the request version when
  supported. On the current v1.0-only server this remains `"1.0"`; after the max is
  raised, `_response` must use the negotiated request version rather than pinning to
  `PROTOCOL_MAX` (`src/respected_orchestrator/interfaces/rpp.py:56`). v1.0 response shape is
  unchanged, although v1.0 clients can observe advertised protocol and manifest values.
- Ops introduced in v1.1 (`lifecycle.*`, `operation.receipt`) requested under
  `rpp: `"1.0"` fail with `UNSUPPORTED_OP` and a hint naming the required version;
  `PROTOCOL_UNSUPPORTED` is reserved for an unsupported `rpp` version. v1.0 clients
  are unaffected because they never send those ops.
- No capability is ever removed or renamed across versions.

## Lifecycle operations (new in v1.1)

Four ops drive the four actions `install`, `update`, `repair`, `uninstall`:

- `lifecycle.plan` - returns an ordered plan and writes no state. Payload:
  `{"action": <one of install/update/repair/uninstall>, "target": {...}}`.
  Result: `{"action", "target", "dry_run": true, "plan": {"steps": [...]}}` where each
  step is `{"id", "action", "summary", "reversible": <bool>, "irreversible_reason":
   <string|null>}`. Steps that cannot be undone set `reversible: false` and a non-null
  `irreversible_reason`, so the dry run exposes irreversible steps before apply.
- `lifecycle.apply` - executes a plan. `operation_id` is required (8..64,
  `[A-Za-z0-9_-]`; reuses the existing `_OPERATION_ID` gate,
  `src/respected_orchestrator/interfaces/rpp.py:27`). Applying the same `operation_id` with an
  identical action and target is idempotent: it returns the stored receipt without
  re-running steps. The same `operation_id` with a different action or target fails
  with `LIFECYCLE_CONFLICT`.
- `lifecycle.status` - returns the receipt for a given `operation_id` (same data as
  `operation.receipt`; provided so a caller that started an op can poll it).
- `lifecycle.rollback` - reverses the applied steps of a prior `operation_id` in
  reverse order. `operation_id` is required. If the plan applied any irreversible step,
  rollback fails with `ROLLBACK_UNAVAILABLE`. Rolling an already-rolled-back op is
  idempotent.

Dry-run is the `lifecycle.plan` op itself: it is read-only, never writes a receipt and
never touches `DATA_ROOT/settings.json` or the workspace.

### Receipts

Every `lifecycle.apply` / `lifecycle.rollback` writes a durable receipt at
`DATA_ROOT/receipts/<operation_id>.json` via the existing `_receipt_path` +
`atomic_write_json` helpers (`src/respected_orchestrator/interfaces/rpp.py:80`,
`src/respected_orchestrator/context.py`), alongside the existing `settings.apply`
receipts. A lifecycle receipt records, in addition to the v1.0 keys, a lifecycle
`status` from the enum:

`planned` -> `in_progress` -> `applied` | `failed` | `rolled_back`

(`planned` is written by an apply that has begun planning-but-not-run only when a plan
already exists; a clean dry run stays in memory). Receipts are queryable by:

- `operation.receipt` - new op; payload `{"operation_id": <string>}` returns the stored
  receipt for either a lifecycle or a `settings.apply` operation. An unknown
  `operation_id` fails with `RECEIPT_NOT_FOUND`.

## Token accounting

Any v1.1 operation that invokes an AI worker, reviewer, or campaign must return and
durably record `usage` with non-negative integer `raw_input_tokens`,
`cached_input_tokens`, `output_tokens`, `reasoning_tokens` and
`estimated_weighted_tokens`. A completed campaign result with missing or invalid usage
must fail verification with `VERIFY_FAILED`; it must never be reported as successfully
applied. Idempotent replay returns the recorded usage without invoking work again or
double-counting tokens. A local lifecycle operation that invokes no model may record
the same usage shape with all values zero.

## New typed errors (v1.1)

Each carries `code`, `message` and `hint`, matching the existing
`RppError(code, message, hint)` shape (`src/respected_orchestrator/interfaces/rpp.py:42`).

| code | raised when | hint |
|---|---|---|
| `UNSUPPORTED_OP` | op exists in a later protocol revision than the request's `rpp` | raise `rpp` to the version that introduced the op |
| `LIFECYCLE_CONFLICT` | an `operation_id` is reused with a different action/target | use a new `operation_id` for a different lifecycle action |
| `LIFECYCLE_PARTIAL` | apply applied some steps, then a later step failed | inspect the receipt, then `lifecycle.rollback` or `lifecycle.repair` |
| `VERIFY_FAILED` | post-apply verification of the result did not pass | inspect the receipt's failed check and re-run `lifecycle.plan` |
| `ROLLBACK_UNAVAILABLE` | rollback requested but an irreversible step was applied | the plan marked the step irreversible; recover manually |
| `PERMISSION_DENIED` | a step needs elevation the caller does not have | grant the required permission and retry the same `operation_id` |
| `RECEIPT_NOT_FOUND` | `operation.receipt` names an unknown `operation_id` | check the operation_id, or the `DATA_ROOT/receipts` directory |

The existing codes `UNKNOWN_OP`, `PROTOCOL_UNSUPPORTED`, `BAD_REQUEST`,
`INVALID_SETTINGS`, `OPERATION_ID_CONFLICT` and `INTERNAL` are unchanged.

## Richer manifest (v1.1)

`manifest` (base shape at `src/respected_orchestrator/interfaces/rpp.py:143`) keeps its v1.0 keys
and adds:

- `installed` (bool) - whether the product is installed at the reported roots.
- `install_state` (string) - one of `absent`, `installed`, `update-available`,
  `repair-needed`.
- `product_version` - the engine version (`__version__`); unchanged key, retained.
- `roots` - paths-only metadata: `{"data": <abs path>, "app": <abs path>, "vault":
  <abs path|null>}`. Absolute path strings only; never contents, never secrets, and the
  paths are not required to exist. `data_root` comes from the `EngineContext`
  (`src/respected_orchestrator/context.py`).
- `capability_details` - per-capability descriptors
  `{"id", "since": "1.0"|"1.1", "ops": [op, ...]}`. The v1.0 `capabilities` list of id
  strings is retained verbatim so v1.0 clients read the same value.

`manifest.capabilities` continues to list only features that exist; a feature without
test evidence is not listed.

## Rules

- No generic shell or filesystem exposure: no op accepts a command line, a path to
  read/write outside the product data root, or an arbitrary target directory. Targets
  are named lifecycle actions only.
- Ops are an explicit allow-list: only keys present in the op registry
  (`_OPS`, `src/respected_orchestrator/interfaces/rpp.py:255`) are dispatchable; anything else is
  `UNKNOWN_OP`. Lifecycle actions are likewise an explicit set
  (`install`/`update`/`repair`/`uninstall`).
- Receipts live only under `DATA_ROOT/receipts/`, resolved through `safe_path`
  (`src/respected_orchestrator/context.py`) which refuses links/reparse points. No
  receipt is written outside the product data root.
- Secrets are never returned: `_redact` (`src/respected_orchestrator/interfaces/rpp.py:88`) still
  applies, and receipts retain only digests/status, never secret values.

## v1.0 feature -> implementation status

| v1.0 feature | Already implemented (citation) | v1.1 change |
|---|---|---|
| `manifest` with capabilities + protocol min/max | `rpp.py:143` (`_manifest`), `rpp.py:19` | additive keys only (roots, installed, capability_details) |
| `health` with real checks | `rpp.py:172` (`_health`) | none |
| `settings.schema` / `settings.validate` | `rpp.py:195`, `rpp.py:199` | none |
| `settings.apply` (atomic write) | `rpp.py:204`, `context.atomic_write_json` | none |
| `settings.readback` | `rpp.py:234` | none |
| operation_id 8..64 `[A-Za-z0-9_-]` | `rpp.py:27`, validated `rpp.py:265` | reused unchanged by lifecycle ops |
| durable receipts + replay/conflict | `rpp.py:80`, `rpp.py:224` (`OPERATION_ID_CONFLICT`) | same mechanism, new `operation.receipt` reader |
| typed errors (6 v1.0 codes) | `rpp.py:42` (`RppError`), `rpp.py:265` (`handle_request`) | +7 new codes |
| secret redaction | `rpp.py:88` (`_redact`) | none |
| protocol min/max | `rpp.py:19` | max raised to `1.1` |

## v1.1 additions (summary)

- version negotiation 1.0..1.1, response echoes the negotiated version.
- ops `lifecycle.plan`, `lifecycle.apply`, `lifecycle.status`, `lifecycle.rollback`,
  `operation.receipt`.
- lifecycle actions `install`, `update`, `repair`, `uninstall` with dry-run plans,
  irreversible-step markers and idempotent `operation_id`s.
- lifecycle receipt `status` enum: `planned`, `in_progress`, `applied`, `failed`,
  `rolled_back`.
- errors `UNSUPPORTED_OP`, `LIFECYCLE_CONFLICT`, `LIFECYCLE_PARTIAL`, `VERIFY_FAILED`,
  `ROLLBACK_UNAVAILABLE`, `PERMISSION_DENIED`, `RECEIPT_NOT_FOUND`.
- manifest `installed`, `install_state`, `roots` (paths only) and `capability_details`.

## Consequences

The change stays additive, so v1.0 tests and callers keep passing unchanged. New
lifecycle tests use temporary directories only and never touch live user data or Git.
The op registry and action set remain closed allow-lists, keeping the no-shell /
no-filesystem-exposure boundary intact.
