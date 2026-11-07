"""Beta.4 fault matrix (B4-08.03): every fault names the tests that inject it and the property that must hold.

    python -m tests.faults.matrix list            # print the matrix
    python -m tests.faults.matrix run OUT.json    # run every referenced test and write commit-linked evidence

The matrix test (test_fault_matrix.py) checks structure and that every referenced test exists; `run` is the slow part that really
executes them (real processes, sandbox, kill/restart) and is what produces release evidence."""
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

D = "tests.faults.test_direct.FaultTests."
E, W = "tests.engine.", "tests.workflows."
AREAS = ("network", "half_written_state", "process_residue", "duplicate_action", "breaker", "apply_safety", "sandbox", "tamper", "escalation")

# id, area, fault, property that must hold, tests
MATRIX = [
    ("F01", "breaker", "a failure repeats forever, for every class, with and without an operator", "retries are bounded; unbounded retry = 0", [D + "test_f01_no_loop_is_unbounded"]),
    ("F02", "breaker", "a policy denial is resumed by a person", "stays a stop", [D + "test_f02_policy_denial_never_resumes"]),
    ("F03", "breaker", "same failure class trips the breaker, a person resumes, the cause is repaired", "opens, passes only with a person, closes for a new class", [D + "test_f03_breaker_open_resume_close", W + "test_recovery.RecoveryTests.test_per_class_caps_open_the_breaker"]),
    ("F04", "network", "the network is unusable", "the whole decision layer still works (no socket opened)", [D + "test_f04_everything_works_offline"]),
    ("F05", "half_written_state", "teams.json is half written", "an error, never a silent default", [D + "test_f05_half_written_team_file", W + "test_team_profiles.ProfileTests.test_unreadable_file_is_an_error_not_a_default"]),
    ("F06", "half_written_state", "the event store ends in a torn record", "earlier handoffs verify, posting continues", [D + "test_f06_torn_event_store_tail", E + "test_journal.JournalTests.test_torn_tail_is_cut_and_the_journal_keeps_working"]),
    ("F07", "duplicate_action", "the same handoff is delivered twice", "stored once, loop decision says duplicate", [D + "test_f07_duplicate_handoff_is_one_event", W + "test_team_loop.TeamLoopTests.test_duplicate_handoff_is_idempotent"]),
    ("F08", "apply_safety", "a recovery or handoff path tries to apply a patch", "no apply action exists in the Beta.4 vocabularies", [D + "test_f08_no_apply_anywhere", W + "test_operator.OperatorTests.test_policy_denial_has_no_way_forward_but_dismiss"]),
    ("F09", "escalation", "an operator approval is moved to another run or replayed", "refused; only a human acts", [D + "test_f09_operator_binding_is_single_case", W + "test_operator.OperatorTests.test_wrong_run_escalation", W + "test_operator.OperatorTests.test_only_a_human_acts_and_nothing_else_may"]),
    ("F10", "duplicate_action", "an activation approval is replayed", "ALREADY_USED", [D + "test_f10_activation_replay", E + "test_capability_activation.ActivationTests.test_happy_path_returns_writes_and_rollback_and_is_single_use"]),
    ("F11", "tamper", "run evidence is forged or unsigned", "never reaches the ledger or the track record", [D + "test_f11_tampered_evidence_is_skipped_by_the_ledger", E + "test_track_record.TrackRecordTests.test_skips_running_custom_and_tampered_evidence"]),
    ("F12", "tamper", "a handoff carries forged evidence, a spoofed sender, wider scope", "rejected with a stable code", [W + "test_handoff.HandoffTests.test_forged_or_missing_evidence", W + "test_handoff.HandoffTests.test_spoofed_sender_and_unknown_actor", W + "test_handoff.HandoffTests.test_scope_can_only_narrow"]),
    ("F13", "escalation", "two roles bounce work back and forth", "max-hop exceeded -> escalate, nothing delivered, no apply", [W + "test_team_loop.TeamLoopTests.test_simulated_job_always_ends", W + "test_team_commands.TeamCommandTests.test_hop_budget_escalates_records_an_event_and_delivers_nothing"]),
    ("F14", "escalation", "a quota failure is resumed after an auth failure", "needs the person's acknowledgement", [W + "test_operator.OperatorTests.test_quota_resumed_without_auth_needs_an_acknowledgement"]),
    ("F15", "tamper", "a capability plan is edited after it was shown", "TAMPERED", [E + "test_capability_activation.ActivationTests.test_tampered_plan_is_rejected", E + "test_capability_activation.ActivationTests.test_stale_inventory_and_changed_target_file"]),
    ("F16", "tamper", "a manifest claims trust or carries undeclared fields", "execution denied, trust unknown", [E + "test_capability_permissions.PermissionTests.test_false_trusted_flag_inside_the_manifest_counts_for_nothing", E + "test_capability_permissions.PermissionTests.test_malicious_manifests_are_denied_with_the_gates_own_code"]),
    ("F17", "process_residue", "a worker spawns children, then times out or is cancelled", "the whole tree is killed", [E + "test_windows_processes.ProcessLifecycleTests.test_timeout_kills_the_whole_tree", E + "test_windows_processes.ProcessLifecycleTests.test_cancel_kills_the_whole_tree_promptly", E + "test_runner.EngineTests.test_timeout_kills_worker_descendants"]),
    ("F18", "process_residue", "the supervisor crashes mid-run", "owned descendants are killed; the run is interrupted, never applied", [E + "test_runner.EngineTests.test_supervisor_crash_kills_owned_descendants", E + "test_maintenance.RunningWorkTests.test_killing_a_running_run_the_hard_way_leaves_it_interrupted_and_never_applied"]),
    ("F19", "half_written_state", "a process is killed at every step of a project run", "resumes once, no duplicate campaign, no second apply", [W + "test_project_resume.ProjectResumeTests.test_kill_after_apply_is_explained_by_the_signed_marker_without_reapplying", W + "test_project_recovery.ProjectRecoveryTests.test_a_kill_mid_stage_resumes_without_a_duplicate_campaign_or_apply"]),
    ("F20", "apply_safety", "an approval token or decision is replayed", "no second apply", ["tests.engine.test_approval_attacks.ApprovalAttackTests.test_11_replayed_token_cannot_apply_twice", "tests.engine.test_approval_attacks.ApprovalAttackTests.test_10_replayed_decision_changes_nothing_a_second_time"]),
    ("F21", "apply_safety", "the project moves between check and apply", "an apply race writes nothing", [E + "test_review_apply_invariants.RejectedReviewApplyInvariantTests.test_04_apply_race_after_precheck_writes_nothing"]),
    ("F22", "sandbox", "an acceptance check or worker tries the network or reads the engine key", "denied (AppContainer)", [E + "test_sandbox.VerifyIsolationTest.test_ip_dns_loopback_and_child_process_egress_are_denied", E + "test_sandbox.VerifyIsolationTest.test_engine_key_and_data_root_are_unreachable_and_the_worktree_works"]),
    ("F23", "duplicate_action", "a run is retried twice", "the second retry is refused; the recovery table has the last word", [W + "test_operator.OperatorTests.test_crash_loop_ends_at_the_attempt_limit_which_no_person_can_lift", E + "test_run_wiring.WiringTests.test_second_timeout_in_a_chain_is_stopped_by_the_recovery_table"]),
    ("F24", "half_written_state", "a checkpoint or lock file is corrupt or half written", "never resumed from, locks reclaimed only when dead", [W + "test_checkpoint.CheckpointTests.test_newer_schema_tamper_broken_json_and_missing_files_are_never_resumed", E + "test_lanes.WriterLockTest.test_stale_writer_lock_of_a_dead_process_is_reclaimed"]),
]


def tests_of(entry):
    return entry[4]


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


def check_structure():
    """Problems with the matrix itself (empty list = fine)."""
    problems, ids = [], [e[0] for e in MATRIX]
    if len(MATRIX) < 20:
        problems.append("fewer than 20 fault fixtures")
    if len(set(ids)) != len(ids):
        problems.append("duplicate fault ids")
    missing_areas = set(AREAS) - {e[1] for e in MATRIX}
    if missing_areas:
        problems.append("areas without a fixture: " + ", ".join(sorted(missing_areas)))
    for entry in MATRIX:
        if not tests_of(entry):
            problems.append(f"{entry[0]} has no test")
        for name in tests_of(entry):
            try:
                suite = unittest.defaultTestLoader.loadTestsFromName(name)
            except (ImportError, AttributeError) as error:
                problems.append(f"{entry[0]}: {name} cannot be loaded ({error})")
                continue
            cases = list(_flatten(suite))
            # Python 3.13 turns a missing test into a placeholder that "fails" only when run; catch it here instead
            if len(cases) != 1 or type(cases[0]).__name__ == "_FailedTest":
                problems.append(f"{entry[0]}: {name} cannot be loaded or is not exactly one test")
    return problems


def run_all():
    started = time.time()
    results = []
    for fault_id, area, fault, holds, names in MATRIX:
        outcome = {"id": fault_id, "area": area, "fault": fault, "must_hold": holds, "tests": []}
        for name in names:
            result = unittest.TextTestRunner(stream=open("nul" if sys.platform == "win32" else "/dev/null", "w"), verbosity=0).run(unittest.defaultTestLoader.loadTestsFromName(name))
            outcome["tests"].append({"test": name, "ok": result.wasSuccessful(), "skipped": len(result.skipped), "failures": len(result.failures) + len(result.errors)})
        outcome["ok"] = all(t["ok"] and not t["skipped"] for t in outcome["tests"])
        results.append(outcome)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    return {"schema": "respected.faults.matrix.v1", "commit": commit, "working_tree_dirty": dirty, "seconds": round(time.time() - started, 1),
            "faults": len(results), "passed": sum(r["ok"] for r in results), "skipped_tests": sum(t["skipped"] for r in results for t in r["tests"]),
            "unbounded_retry": 0 if all(r["ok"] for r in results if r["id"] == "F01") else "unproven",
            "double_apply": 0 if all(r["ok"] for r in results if r["area"] == "apply_safety") else "unproven", "results": results}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["list"]:
        for e in MATRIX:
            print(f"{e[0]} [{e[1]}] {e[2]} -> {e[3]}")
        return 0
    if argv[:1] == ["run"] and len(argv) == 2:
        problems = check_structure()
        if problems:
            print("matrix problems:", "; ".join(problems))
            return 2
        report = run_all()
        Path(argv[1]).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{report['passed']}/{report['faults']} faults hold; skipped={report['skipped_tests']}; wrote {argv[1]}")
        return 0 if report["passed"] == report["faults"] and not report["skipped_tests"] else 1
    print("usage: python -m tests.faults.matrix list | run OUT.json")
    return 2


if __name__ == "__main__":
    sys.exit(main())
