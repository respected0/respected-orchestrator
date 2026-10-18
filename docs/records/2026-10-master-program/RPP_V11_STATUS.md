# RPP v1.1 implementation status (2026-10)

Evidence record. Sibling repos read read-only; no code changed. Contract is
`docs/decisions/RPP_V1_1.md` (additive to v1.0 `docs/decisions/RPP_V1.md`).

v1.1 surface = version negotiation (1.0..1.1), five lifecycle/receipt ops
(`lifecycle.plan|apply|status|rollback`, `operation.receipt`), durable receipts queried
by `operation.receipt`, and seven new typed errors (`UNSUPPORTED_OP`,
`LIFECYCLE_CONFLICT`, `LIFECYCLE_PARTIAL`, `VERIFY_FAILED`, `ROLLBACK_UNAVAILABLE`,
`PERMISSION_DENIED`, `RECEIPT_NOT_FOUND`).

## Respected Orchestrator (this repo) - v1.1 complete
- Negotiation: `PROTOCOL_MAX="1.1"` (`src/respected_orchestrator/rpp.py:21`); response
  echoes the negotiated request version (`rpp.py:57,367`). Tests
  `tests/test_rpp.py::test_v11_request_echoes_negotiated_version`,
  `::test_v10_request_still_supported`, `::test_protocol_unsupported_boundaries`.
- Lifecycle ops registered (`rpp.py:323`) and gated to 1.1 (`rpp.py:338,373-375`).
  Implementation `src/respected_orchestrator/lifecycle.py`: `plan` (:185), `apply`
  (:327, idempotent + `LIFECYCLE_CONFLICT` :341), `rollback` (:372), `receipt` (:211).
  Tests `tests/test_rpp_lifecycle.py` (plan read-only, apply/receipt, idempotent replay,
  conflict, journal resume, uninstall, rollback, repair, status, irreversible step,
  unsafe-path rejection); `tests/test_rpp.py::test_v11_ops_require_v11` asserts
  `UNSUPPORTED_OP`.
- Receipts: durable under `DATA_ROOT/receipts`; `operation.receipt` reads lifecycle or
  `settings.apply` receipts (`rpp.py:307`; tests
  `test_operation_receipt_reads_settings_receipt`, `test_receipt_not_found`). Apply
  receipts carry zeroed `usage` (`lifecycle.py:36,354`).
- Typed errors: all seven present (`rpp.py:375` UNSUPPORTED_OP; `lifecycle.py` :341
  LIFECYCLE_CONFLICT, :308 LIFECYCLE_PARTIAL, :319 VERIFY_FAILED, :380/:388
  ROLLBACK_UNAVAILABLE, :254/:314 PERMISSION_DENIED, :215 RECEIPT_NOT_FOUND).

## Respected SecondBrain - v1.1 present, partially delegated
- Negotiation: `PROTOCOL_MAX="1.1"` (`respected-secondbrain/src/respectedbrain/rpp.py:23`);
  only 1.0/1.1 accepted (`rpp.py:438`). Test
  `tests/test_rpp.py::test_v11_negotiation_echoes_requested_version`.
- Lifecycle ops: `_V11_OPS` + 1.1 gate (`rpp.py:373-399`); logic in
  `src/respectedbrain/rpp_lifecycle.py` (`plan` :66, `apply` :165, `rollback` :195).
  Tests `tests/test_rpp_lifecycle.py` (plan read-only/irreversible, repair receipt,
  idempotent replay, conflict, status, rollback idempotent/refusal, engine delegation).
- Not implemented / gaps: `install` and `update` cannot run - `_delegate` raises
  `PERMISSION_DENIED` because RPP takes no package path (`rpp_lifecycle.py:129`).
  `rollback` only writes `rolled_back` state, never reverses files (shortcut,
  `rpp_lifecycle.py:210`). Receipts carry no `usage`; `VERIFY_FAILED` is never raised.
  Manifest rich keys are present (`rpp.py:118-121`).
- Receipts query: `operation.receipt`/`lifecycle.status` (`rpp.py:334,360`); unknown id
  -> `RECEIPT_NOT_FOUND`. Test `::test_status_matches_receipt_and_unknown_is_not_found`.

## Respected Hub (client) - v1.0 only
- Rust backend pins `RPP_VERSION="1.0"` (`respected-hub/src-tauri/src/rpp.rs:10`) and
  allow-lists six v1.0 ops (`rpp.rs:12`); `rpp_call` always runs at 1.0 (`rpp.rs:102`).
  `normalize` rebuilds the envelope with "1.0", ignoring the engine's echoed version
  (`rpp.rs:77,98`). No lifecycle/receipt op is reachable. Rust `mod tests` cover
  op/product rejection, engine-not-found and id/secret filtering - not lifecycle.
- TypeScript contract pins `RPP_VERSION='1.0'` (`respected-hub/src/rpp.ts:4`);
  `parseResponse` rejects any response whose `rpp !== '1.0'` (`rpp.ts:67`), so it cannot
  consume a 1.1 echo. `negotiate` compares ranges, but the hub side is 1.0..1.0
  (`rpp.ts:102,104`); the plain-error map lists no v1.1 codes (`rpp.ts:130`). Tests
  `tests/rpp.test.ts` exercise 1.0 shapes and `negotiate` only; no 1.1 case.
- Consequence: the Hub works against v1.0 requests today (products echo 1.0 for those),
  but cannot negotiate, call or describe any v1.1 element.