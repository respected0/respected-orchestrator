# Lane Summary Review

Date: 2026-10-12

## Verdict

Approved with one hardening change. The lane-summary refinement correctly preserves the signed run’s specific failure reason, and invalid or absent signed status now falls back to the MAF reason.

## Root Cause

`run_maf_slice` collapses any incomplete worker to the generic `worker_failed` reason. Campaign summaries copied that label even when the final run’s signed `status.json` contained the actual cause, such as `scope_violation` or `timed_out`.

## Review Findings

- A genuine worker failure is not mislabeled: when the signed run reason is itself `worker_failed`, the summary retains that reason.
- Missing, malformed, or signature-invalid `status.json` does not raise out of `_lane_summary`; it falls back to the generic MAF reason and the lane remains failed.
- A validly signed status copied into another run directory is now rejected unless its `run_id` equals the lane’s `final_run_id`. This closes a relocation gap that content-only HMAC verification did not cover.
- No reviewed consumer branches on the old generic value. `project.py` includes the reason in its failure message, and the campaign final prompt passes lane summaries as diagnostic evidence.
- A non-approved lane still receives a reason: signed refinement, the MAF reason, the last attempt reason, the output status, or `unknown`, in that order.

## Residual Risks

- Signed status values remain trusted after HMAC and run-ID validation; a future status producer that writes a misleading reason can still propagate that reason.
- For review outcomes such as `HUMAN_APPROVAL_REQUIRED`, a signed `completed` run status may be used as the diagnostic reason when MAF provides no reason. This describes the underlying run but not the reviewer decision.
- Acceptance tests were not run in this sandbox because the worker environment explicitly forbids launching Python.

